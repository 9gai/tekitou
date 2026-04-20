"""
DBに保存済みのコメントのみコミットから，コメント・対象コード・メタデータを抽出する。

改善点:
  - リポジトリ単位でクローン（1リポジトリにつき1回のクローン）
  - get_code_origin を git blame に置き換えて高速化

使用方法:
    python extract_data.py [--db dataset.db] [--clone-dir /tmp/coc_extract]
"""

import argparse
import hashlib
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import git
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
    """コメントが追加された行番号から，所属メソッドと所属クラスを返す。"""
    lines = source.splitlines()
    target_line = min(line_no - 1, len(lines) - 1)

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

    depth = 0
    method_end = method_start
    for i in range(method_start, len(lines)):
        depth += lines[i].count("{") - lines[i].count("}")
        if depth <= 0 and i > method_start:
            method_end = i
            break

    method_text = "\n".join(lines[method_start:method_end + 1])

    class_name = ""
    for i in range(method_start, -1, -1):
        m = re.search(r"\bclass\s+(\w+)", lines[i])
        if m:
            class_name = m.group(1)
            break

    return method_text, class_name


def get_code_origin_blame(local_path: Path, file_path: str, line_no: int, commit_hash: str) -> tuple[str, str, str]:
    """
    git blame --porcelain でコメント挿入位置の起源コミット・日時・著者メールを1回のコマンドで取得する。
    Returns: (intro_hash, intro_date_iso, author_email)
    """
    try:
        result = subprocess.run(
            ["git", "blame", "-L", f"{line_no},{line_no}", "--porcelain",
             f"{commit_hash}^", "--", file_path],
            cwd=str(local_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return "", "", ""

        lines = result.stdout.splitlines()
        intro_hash = lines[0].split()[0]

        # --porcelain 出力からメタデータを直接抽出（追加のgit呼び出し不要）
        author_email = ""
        committer_time = ""
        committer_tz = ""
        for line in lines[1:]:
            if line.startswith("author-mail "):
                author_email = line[len("author-mail "):].strip("<>")
            elif line.startswith("committer-time "):
                committer_time = line[len("committer-time "):]
            elif line.startswith("committer-tz "):
                committer_tz = line[len("committer-tz "):]

        # Unixタイムスタンプ + タイムゾーン → ISO形式
        intro_date = ""
        if committer_time and committer_tz:
            import re as _re
            from datetime import timedelta, timezone
            m = _re.match(r"([+-])(\d{2})(\d{2})", committer_tz.strip())
            if m:
                sign = 1 if m.group(1) == "+" else -1
                tz_offset = timezone(timedelta(
                    hours=sign * int(m.group(2)),
                    minutes=sign * int(m.group(3)),
                ))
                intro_date = datetime.fromtimestamp(int(committer_time), tz=tz_offset).isoformat()

        return intro_hash, intro_date, author_email

    except Exception:
        return "", "", ""


def compute_time_gap(intro_date_str: str, comment_date_str: str) -> float:
    if not intro_date_str or not comment_date_str:
        return -1.0
    try:
        d1 = datetime.fromisoformat(intro_date_str)
        d2 = datetime.fromisoformat(comment_date_str)
        return (d2 - d1).total_seconds() / 86400
    except Exception:
        return -1.0


def process_commit(conn, commit_row: dict, local_path: Path) -> None:
    commit_id = commit_row["id"]
    commit_hash = commit_row["commit_hash"]
    commit_date = commit_row["commit_date"]
    commit_message = commit_row["commit_message"] or ""
    author_id = commit_row["author_id"]
    has_keyword = int(has_clarify_keyword(commit_message))

    for commit in Repository(str(local_path), single=commit_hash).traverse_commits():
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

                intro_hash, intro_date, intro_author_email = get_code_origin_blame(
                    local_path, mf.filename, first_line_no, commit_hash
                )
                time_gap = compute_time_gap(intro_date, commit_date)

                original_author_id = anonymize(intro_author_email) if intro_author_email else ""
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
                    cyclomatic_complexity=None,
                    cognitive_complexity=None,
                    loc=None,
                    parameter_count=None,
                    avg_identifier_length=None,
                    abbrev_ratio=None,
                )
    conn.commit()


def process_repo(repo_name: str, clone_url: str, commit_rows: list[dict], db_path: Path, clone_dir: Path) -> int:
    """1リポジトリ分のコミットをまとめてクローン→処理→削除。"""
    local_path = clone_dir / repo_name.replace("/", "_")
    local_path.mkdir(parents=True, exist_ok=True)
    count = 0

    try:
        git.Repo.clone_from(clone_url, str(local_path))

        for commit_row in commit_rows:
            try:
                with get_connection(db_path) as conn:
                    process_commit(conn, commit_row, local_path)
                count += 1
            except Exception as e:
                msg = f"  [ERROR] commit {commit_row['commit_hash']}: {e}"
                tqdm.write(msg.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))
    finally:
        shutil.rmtree(local_path, ignore_errors=True)

    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--clone-dir", type=Path, default=Path(tempfile.gettempdir()) / "coc_extract")
    args = parser.parse_args()

    args.clone_dir.mkdir(parents=True, exist_ok=True)

    with get_connection(args.db) as conn:
        rows = conn.execute(
            "SELECT c.*, r.repo, r.clone_url FROM commits c "
            "JOIN repos r ON c.repo_id = r.id "
            "WHERE NOT EXISTS (SELECT 1 FROM comments cm WHERE cm.commit_id = c.id)"
        ).fetchall()
        commits = [dict(row) for row in rows]

    print(f"{len(commits)} 件の未処理コミットを処理します ...")

    # リポジトリ単位でグループ化
    repo_commits: dict[str, list[dict]] = defaultdict(list)
    repo_clone_url: dict[str, str] = {}
    for row in commits:
        repo_commits[row["repo"]].append(row)
        repo_clone_url[row["repo"]] = row["clone_url"]

    for repo_name in tqdm(repo_commits, desc="リポジトリ処理中"):
        commit_rows = repo_commits[repo_name]
        try:
            n = process_repo(repo_name, repo_clone_url[repo_name], commit_rows, args.db, args.clone_dir)
            msg = f"  {repo_name}: {n}/{len(commit_rows)} 件処理"
            tqdm.write(msg.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))
        except Exception as e:
            msg = f"  [ERROR] {repo_name}: {e}"
            tqdm.write(msg.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))

    print("完了")


if __name__ == "__main__":
    main()
