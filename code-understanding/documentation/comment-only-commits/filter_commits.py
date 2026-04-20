"""
repos.csvのリポジトリをクローンしてコメントのみコミットを検出し，DBに保存する。

使用方法:
    python filter_commits.py [--repos repos.csv] [--db dataset.db] [--clone-dir /tmp/repos]
"""

import argparse
import csv
import hashlib
import shutil
import tempfile
from pathlib import Path

from pydriller import Repository
from tqdm import tqdm

from utils.comment_detector import (
    has_clarify_keyword,
    has_generated_annotation,
    has_issue_reference,
    is_comment_line,
    is_test_file,
)
from utils.db import get_connection, initialize, insert_commit, insert_repo

DEFAULT_DB = Path(__file__).parent / "dataset.db"
DEFAULT_REPOS = Path(__file__).parent / "repos.csv"


def anonymize(value: str) -> str:
    """メールアドレス等を一方向ハッシュで匿名化する。"""
    return hashlib.sha256(value.encode()).hexdigest()[:16] if value else ""


def is_comment_only_commit(commit) -> bool:
    """
    コミットがコメントのみコミットかを判定する。
    条件:
      - 変更ファイルがすべて .java
      - テストファイル・自動生成ファイルを除外
      - 追加行がすべてコメント行または空白行
      - コード行の削除がゼロ（コメント行の削除は許容）
    """
    modified = commit.modified_files
    if not modified:
        return False

    for mf in modified:
        if not mf.filename.endswith(".java"):
            return False
        if is_test_file(mf.filename):
            return False
        if mf.source_code and has_generated_annotation(mf.source_code):
            return False

        added_lines = [line for _, line in (mf.diff_parsed.get("added") or [])]
        deleted_lines = [line for _, line in (mf.diff_parsed.get("deleted") or [])]

        # 追加行はすべてコメント行または空白行
        if not added_lines:
            return False
        if not all(is_comment_line(line) for line in added_lines):
            return False

        # コード行の削除はゼロ
        if any(not is_comment_line(line) for line in deleted_lines):
            return False

    return True


def process_repo(repo_row: dict, db_path: Path, clone_dir: Path, issue_only: bool = False) -> int:
    repo_name = repo_row["repo"]
    clone_url = repo_row["clone_url"]

    local_path = clone_dir / repo_name.replace("/", "_")
    local_path.mkdir(parents=True, exist_ok=True)
    count = 0

    try:
        with get_connection(db_path) as conn:
            repo_id = insert_repo(
                conn,
                repo=repo_name,
                clone_url=clone_url,
                stars=int(repo_row.get("stars", 0)),
                last_updated=repo_row.get("last_updated", ""),
            )
            conn.commit()

        for commit in Repository(clone_url, clone_repo_to=str(local_path)).traverse_commits():
            if not is_comment_only_commit(commit):
                continue

            issue_ref = int(has_issue_reference(commit.msg))
            if issue_only and not issue_ref:
                continue

            with get_connection(db_path) as conn:
                insert_commit(
                    conn,
                    repo_id=repo_id,
                    commit_hash=commit.hash,
                    commit_date=commit.committer_date.isoformat(),
                    commit_message=commit.msg,
                    author_id=anonymize(commit.author.email),
                    has_issue_ref=issue_ref,
                )
                conn.commit()
            count += 1

    finally:
        shutil.rmtree(local_path, ignore_errors=True)

    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos", type=Path, default=DEFAULT_REPOS)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--clone-dir", type=Path, default=Path(tempfile.gettempdir()) / "coc_repos")
    parser.add_argument("--issue-only", action="store_true",
                        help="issueへの参照（fixes #123 等）を含むコミットのみ収集する")
    args = parser.parse_args()

    args.clone_dir.mkdir(parents=True, exist_ok=True)
    initialize(args.db)

    with args.repos.open(encoding="utf-8") as f:
        repos = list(csv.DictReader(f))

    # 処理済みリポジトリをスキップ
    with get_connection(args.db) as conn:
        done = {r[0] for r in conn.execute("SELECT repo FROM repos").fetchall()}

    total = 0
    for row in tqdm(repos, desc="リポジトリ処理中"):
        if row["repo"] in done:
            continue
        try:
            n = process_repo(row, args.db, args.clone_dir, issue_only=args.issue_only)
            total += n
            tqdm.write(f"  {row['repo']}: {n} 件のコメントのみコミットを検出")
        except Exception as e:
            msg = f"  [ERROR] {row['repo']}: {e}"
            tqdm.write(msg.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))

    print(f"\n完了: 合計 {total} 件のコメントのみコミットを検出しました。")


if __name__ == "__main__":
    main()
