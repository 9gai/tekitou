"""
issue_complexity=1 のコメントが追加されたファイル（同commit・同file）から
コメントが追加されなかったメソッドを負例として収集する。

手順:
  1. unique (repo, commit_hash, file_path) を取得
  2. GitHub API でそのcommitのファイル内容を取得
  3. Lizard で全メソッドを抽出
  4. 正例（commentsテーブルに存在するメソッド）を除外
  5. 残りを負例として negative_samples テーブルに保存

使用方法:
    python build_negative_samples.py [--db dataset.db] [--limit N]
"""

import argparse
import base64
import os
import tempfile
import time
from pathlib import Path

import lizard
from dotenv import load_dotenv
from github import Github, GithubException, RateLimitExceededException
from tqdm import tqdm

from annotate import compute_identifier_metrics
from annotate_signature import extract_signature_features
from utils.db import get_connection

load_dotenv(Path(__file__).parent / ".env")

DEFAULT_DB = Path(__file__).parent / "dataset.db"

NEGATIVE_SCHEMA = """
CREATE TABLE IF NOT EXISTS negative_samples (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    repo                   TEXT NOT NULL,
    commit_hash            TEXT NOT NULL,
    file_path              TEXT NOT NULL,
    method_name            TEXT,
    cyclomatic_complexity  REAL,
    loc                    INTEGER,
    parameter_count        INTEGER,
    avg_identifier_length  REAL,
    abbrev_ratio           REAL,
    is_public              INTEGER,
    return_type_primitive  INTEGER,
    method_name_word_count INTEGER,
    throws_count           INTEGER
);
"""


def wait_for_rate_limit(g: Github) -> None:
    reset = g.get_rate_limit().core.reset
    wait = max((reset - time.time()), 0) + 5
    tqdm.write(f"  Rate limit. Waiting {wait:.0f}s ...")
    time.sleep(wait)


def get_file_content(
    g: Github,
    repo_name: str,
    filename: str,
    commit_sha: str,
    _tree_cache: dict | None = None,
) -> str | None:
    """
    GitHub API でコミット時点のファイル内容を取得する。
    file_path はファイル名のみなので、ツリーを検索してフルパスを解決する。
    _tree_cache は (repo_name, commit_sha) → {filename: full_path} のキャッシュ。
    """
    if _tree_cache is None:
        _tree_cache = {}

    cache_key = (repo_name, commit_sha)
    if cache_key not in _tree_cache:
        # ツリーを取得してキャッシュ
        mapping: dict[str, str] = {}
        while True:
            try:
                repo = g.get_repo(repo_name)
                commit = repo.get_commit(commit_sha)
                tree = repo.get_git_tree(commit.commit.tree.sha, recursive=True)
                for elem in tree.tree:
                    # basename → full path
                    basename = elem.path.rsplit("/", 1)[-1]
                    if basename.endswith(".java"):
                        mapping[basename] = elem.path
                break
            except RateLimitExceededException:
                wait_for_rate_limit(g)
            except GithubException:
                break
        _tree_cache[cache_key] = mapping

    full_path = _tree_cache[cache_key].get(filename)
    if not full_path:
        return None

    while True:
        try:
            repo = g.get_repo(repo_name)
            content = repo.get_contents(full_path, ref=commit_sha)
            if isinstance(content, list):
                return None
            return base64.b64decode(content.content).decode("utf-8", errors="replace")
        except RateLimitExceededException:
            wait_for_rate_limit(g)
        except GithubException:
            return None


def extract_methods_from_source(source: str) -> list[dict]:
    """
    Lizard でファイルを解析し、全メソッドの情報を返す。
    各メソッドは {name, start_line, end_line, cc, params, source} を持つ。
    """
    with tempfile.NamedTemporaryFile(
        suffix=".java", mode="w", encoding="utf-8", delete=False
    ) as f:
        f.write(source)
        tmp_path = f.name

    methods = []
    try:
        result = lizard.analyze_file(tmp_path)
        if not result:
            return methods
        source_lines = source.splitlines()
        for fn in result.function_list:
            start = fn.start_line - 1
            end = fn.end_line
            method_src = "\n".join(source_lines[start:end])
            methods.append({
                "name": fn.name,
                "start_line": fn.start_line,
                "end_line": fn.end_line,
                "cc": fn.cyclomatic_complexity,
                "params": fn.parameter_count,
                "loc": fn.length,
                "source": method_src,
            })
    except Exception:
        pass
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return methods


def signature_key(method_src: str) -> str:
    """
    メソッドの最初のシグネチャ行からマッチング用キーを生成する。
    空白を正規化して比較する。
    """
    for line in method_src.splitlines():
        s = line.strip()
        if not s or s.startswith("*") or s.startswith("/") or s.startswith("@"):
            continue
        # 空白を正規化
        import re
        return re.sub(r"\s+", " ", s)
    return ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--limit", type=int, default=None,
                        help="処理するファイル数の上限（デバッグ用）")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise EnvironmentError("GITHUB_TOKEN が設定されていません。")
    g = Github(token)

    # negative_samples テーブルを初期化
    conn = get_connection(args.db)
    conn.executescript(NEGATIVE_SCHEMA)
    conn.commit()

    # 処理済みの (repo, commit_hash, file_path) をスキップ
    done = set()
    for row in conn.execute(
        "SELECT DISTINCT repo, commit_hash, file_path FROM negative_samples"
    ).fetchall():
        done.add((row["repo"], row["commit_hash"], row["file_path"]))

    # 対象の (repo, commit_hash, file_path) を取得
    targets = conn.execute("""
        SELECT DISTINCT r.repo, c2.commit_hash, c.file_path
        FROM comments c
        JOIN commits c2 ON c.commit_id = c2.id
        JOIN repos r ON c2.repo_id = r.id
        WHERE c2.issue_complexity = 1
          AND c.file_path IS NOT NULL
    """).fetchall()

    # 正例のシグネチャキーを (repo, commit_hash, file_path) ごとに収集
    positive_keys: dict[tuple, set[str]] = {}
    for row in conn.execute("""
        SELECT r.repo, c2.commit_hash, c.file_path, c.target_method
        FROM comments c
        JOIN commits c2 ON c.commit_id = c2.id
        JOIN repos r ON c2.repo_id = r.id
        WHERE c2.issue_complexity = 1
          AND c.file_path IS NOT NULL
          AND c.target_method IS NOT NULL
    """).fetchall():
        key = (row["repo"], row["commit_hash"], row["file_path"])
        positive_keys.setdefault(key, set()).add(signature_key(row["target_method"]))

    conn.close()

    if args.limit:
        targets = targets[: args.limit]

    to_process = [t for t in targets if (t["repo"], t["commit_hash"], t["file_path"]) not in done]
    print(f"{len(to_process)} ファイルを処理します（スキップ: {len(done)}）")

    BATCH_SIZE = 100
    batch: list[tuple] = []

    def flush(batch, db_path):
        if not batch:
            return
        c = get_connection(db_path)
        c.executemany("""
            INSERT INTO negative_samples
            (repo, commit_hash, file_path, method_name,
             cyclomatic_complexity, loc, parameter_count,
             avg_identifier_length, abbrev_ratio,
             is_public, return_type_primitive,
             method_name_word_count, throws_count)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, batch)
        c.commit()
        c.close()
        batch.clear()

    tree_cache: dict = {}

    for target in tqdm(to_process, desc="負例収集中"):
        repo = target["repo"]
        commit_hash = target["commit_hash"]
        file_path = target["file_path"]
        file_key = (repo, commit_hash, file_path)

        source = get_file_content(g, repo, file_path, commit_hash, tree_cache)
        if not source:
            continue

        methods = extract_methods_from_source(source)
        pos_keys = positive_keys.get(file_key, set())

        for m in methods:
            sig_k = signature_key(m["source"])
            if sig_k in pos_keys:
                continue  # 正例はスキップ

            avg_len, abbrev = compute_identifier_metrics(m["source"])
            is_pub, rt_prim, wc, tc = extract_signature_features(m["source"])

            batch.append((
                repo, commit_hash, file_path, m["name"],
                m["cc"], m["loc"], m["params"],
                avg_len, abbrev,
                is_pub, rt_prim, wc, tc,
            ))

        if len(batch) >= BATCH_SIZE:
            flush(batch, args.db)

    flush(batch, args.db)

    # 結果サマリ
    import sys
    conn = get_connection(args.db)
    total = conn.execute("SELECT COUNT(*) FROM negative_samples").fetchone()[0]
    sys.stdout.buffer.write(f"\n負例総数: {total}\n".encode())

    features = ["cyclomatic_complexity", "loc", "parameter_count",
                "avg_identifier_length", "abbrev_ratio",
                "is_public", "return_type_primitive",
                "method_name_word_count", "throws_count"]
    sys.stdout.buffer.write(b"\n=== negative_samples feature means ===\n")
    for feat in features:
        row = conn.execute(
            f"SELECT AVG({feat}), MIN({feat}), MAX({feat}) FROM negative_samples WHERE {feat} IS NOT NULL"
        ).fetchone()
        avg_s = f"{row[0]:.3f}" if row[0] is not None else "N/A"
        sys.stdout.buffer.write(
            f"  {feat:30s}: avg={avg_s} min={row[1]} max={row[2]}\n".encode()
        )
    conn.close()


if __name__ == "__main__":
    main()
