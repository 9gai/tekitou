"""
DBに保存済みのコメントのみコミットから，コメント・対象コード・メタデータを抽出する。

使用方法:
    python extract_data.py [--db dataset.db]
"""

import argparse
import hashlib
import re
from datetime import datetime
from pathlib import Path

from pydriller import Repository
from tqdm import tqdm

from utils.comment_detector import classify_comment, has_clarify_keyword
from utils.db import get_connection, insert_comment

DEFAULT_DB = Path(__file__).parent / "dataset.db"

METHOD_PATTERN = re.compile(
    r"((?:(?:public|private|protected|static|final|synchronized|abstract|native)\s+)*"
    r"[\w<>\[\]]+\s+\w+\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{)",
    re.MULTILINE,
)


def anonymize(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16] if value else ""


def extract_method_context(source: str, line_no: int) -> tuple[str, str]:
    """
    コメントが追加された行番号から，所属メソッドと所属クラスを返す。
    簡易的な実装：メソッドシグネチャの検索に正規表現を使用。
    """
    lines = source.splitlines()
    target_line = min(line_no - 1, len(lines) - 1)

    # 上方向にメソッド開始を探す
    method_start = None
    brace_depth = 0
    for i in range(target_line, -1, -1):
        line = lines[i]
        brace_depth += line.count("}") - line.count("{")
        if METHOD_PATTERN.search(line) and brace_depth <= 0:
            method_start = i
            break

    if method_start is None:
        return "", ""

    # メソッド終端を探す（単純な波括弧カウント）
    depth = 0
    method_end = method_start
    for i in range(method_start, len(lines)):
        depth += lines[i].count("{") - lines[i].count("}")
        if depth <= 0 and i > method_start:
            method_end = i
            break

    method_text = "\n".join(lines[method_start:method_end + 1])

    # クラス名を上方向から探す
    class_name = ""
    for i in range(method_start, -1, -1):
        m = re.search(r"\bclass\s+(\w+)", lines[i])
        if m:
            class_name = m.group(1)
            break

    return method_text, class_name


def get_code_origin(repo_url: str, file_path: str, line_no: int, before_hash: str) -> tuple[str, str]:
    """
    対象行を最初に追加したコミットを git log --follow -S で近似する。
    PyDrillerで before_hash 以前のコミットを逆順に走査する。
    """
    for commit in Repository(repo_url, to_commit=before_hash).traverse_commits():
        for mf in commit.modified_files:
            if mf.filename != Path(file_path).name:
                continue
            added = [ln for ln, _ in (mf.diff_parsed.get("added") or [])]
            if line_no in added:
                return commit.hash, commit.committer_date.isoformat()
    return "", ""


def compute_time_gap(intro_date_str: str, comment_date_str: str) -> float:
    if not intro_date_str or not comment_date_str:
        return -1.0
    try:
        fmt = "%Y-%m-%dT%H:%M:%S%z"
        d1 = datetime.fromisoformat(intro_date_str)
        d2 = datetime.fromisoformat(comment_date_str)
        return (d2 - d1).total_seconds() / 86400
    except Exception:
        return -1.0


def process_commit(conn, commit_row: dict) -> None:
    commit_id = commit_row["id"]
    repo_clone_url = conn.execute(
        "SELECT clone_url FROM repos WHERE id = (SELECT repo_id FROM commits WHERE id = ?)",
        (commit_id,),
    ).fetchone()["clone_url"]

    commit_hash = commit_row["commit_hash"]
    commit_date = commit_row["commit_date"]
    commit_message = commit_row["commit_message"] or ""
    author_id = commit_row["author_id"]
    has_keyword = int(has_clarify_keyword(commit_message))

    for commit in Repository(repo_clone_url, single=commit_hash).traverse_commits():
        for mf in commit.modified_files:
            if not mf.filename.endswith(".java"):
                continue

            added_lines = mf.diff_parsed.get("added") or []
            if not added_lines:
                continue

            # 連続するコメント行をグループ化
            groups: list[list[tuple[int, str]]] = []
            current: list[tuple[int, str]] = []
            prev_no = -2
            for line_no, line in added_lines:
                if line_no == prev_no + 1:
                    current.append((line_no, line))
                else:
                    if current:
                        groups.append(current)
                    current = [(line_no, line)]
                prev_no = line_no
            if current:
                groups.append(current)

            source = mf.source_code or ""
            for group in groups:
                first_line_no = group[0][0]
                comment_text = "\n".join(line for _, line in group)
                comment_type = classify_comment([line for _, line in group])

                method_text, class_name = extract_method_context(source, first_line_no)

                intro_hash, intro_date = get_code_origin(
                    repo_clone_url, mf.filename, first_line_no, commit_hash
                )
                time_gap = compute_time_gap(intro_date, commit_date)

                # 元作者の特定（intro_hash が取れた場合）
                original_author_id = ""
                if intro_hash:
                    for c in Repository(repo_clone_url, single=intro_hash).traverse_commits():
                        original_author_id = anonymize(c.author.email)
                is_different = int(original_author_id != author_id) if original_author_id else -1

                insert_comment(
                    conn,
                    commit_id=commit_id,
                    file_path=mf.filename,
                    added_comment=comment_text,
                    comment_type=comment_type,
                    target_method=method_text,
                    target_class=class_name,
                    code_intro_commit=intro_hash,
                    code_intro_date=intro_date,
                    time_gap_days=time_gap,
                    original_author_id=original_author_id,
                    is_different_author=is_different,
                    message_has_clarify_keyword=has_keyword,
                    # annotate.py で埋める
                    cyclomatic_complexity=None,
                    cognitive_complexity=None,
                    loc=None,
                    parameter_count=None,
                    avg_identifier_length=None,
                    abbrev_ratio=None,
                )
        conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    with get_connection(args.db) as conn:
        commits = conn.execute(
            "SELECT c.* FROM commits c "
            "WHERE NOT EXISTS (SELECT 1 FROM comments cm WHERE cm.commit_id = c.id)"
        ).fetchall()

    print(f"{len(commits)} 件のコミットを処理します ...")

    for row in tqdm(commits, desc="データ抽出中"):
        try:
            with get_connection(args.db) as conn:
                process_commit(conn, dict(row))
        except Exception as e:
            tqdm.write(f"  [ERROR] commit {row['commit_hash']}: {e}")

    print("完了")


if __name__ == "__main__":
    main()
