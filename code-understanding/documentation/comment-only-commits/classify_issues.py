"""
issue紐づきのコメントのみコミットを対象に，GitHub APIでissue内容を取得し，
コードの難解さに関するものかを分類してDBに記録する。

使用方法:
    python classify_issues.py [--db dataset.db]

環境変数:
    GITHUB_TOKEN: GitHub personal access token（rate limit対策）
"""

import argparse
import csv
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from github import Github, GithubException, RateLimitExceededException
from tqdm import tqdm

from utils.comment_detector import extract_issue_numbers, is_complexity_related
from utils.db import get_connection, initialize

load_dotenv(Path(__file__).parent / ".env")

DEFAULT_DB = Path(__file__).parent / "dataset.db"


def fetch_issue_text(g: Github, repo_name: str, issue_number: int) -> str | None:
    """issueのタイトルと本文を結合して返す。取得失敗時はNone。"""
    try:
        repo = g.get_repo(repo_name)
        issue = repo.get_issue(issue_number)
        return f"{issue.title}\n{issue.body or ''}"
    except RateLimitExceededException:
        raise
    except GithubException:
        return None


def wait_for_rate_limit(g: Github) -> None:
    reset = g.get_rate_limit().core.reset
    wait = max((reset - time.time()), 0) + 5
    tqdm.write(f"  Rate limit exceeded. Waiting {wait:.0f}s ...")
    time.sleep(wait)


def _import_csv(csv_path: Path, db_path: Path) -> None:
    """CSVの分類結果をDBに反映する。DBがロックされていれば手動実行用として使える。"""
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [(int(r["issue_complexity"]), int(r["commit_id"])) for r in reader]

    conn = get_connection(db_path)
    try:
        conn.executemany(
            "UPDATE commits SET issue_complexity = ? WHERE id = ?", rows
        )
        conn.commit()
        print(f"DB更新完了: {len(rows)} 件")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "issue_complexity.csv",
                        help="分類結果の保存先CSV（DBロック回避のための中間ファイル）")
    parser.add_argument("--import-only", action="store_true",
                        help="--out のCSVをDBにインポートするだけ（API呼び出しをスキップ）")
    args = parser.parse_args()

    initialize(args.db)

    # --import-only: CSVをDBに取り込むだけ
    if args.import_only:
        _import_csv(args.out, args.db)
        return

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise EnvironmentError("GITHUB_TOKEN が設定されていません。")
    g = Github(token)

    read_conn = get_connection(args.db)
    rows = read_conn.execute(
        "SELECT c.id, c.commit_message, r.repo "
        "FROM commits c JOIN repos r ON c.repo_id = r.id "
        "WHERE c.issue_complexity IS NULL "
        "AND c.commit_message LIKE '%#%'"
    ).fetchall()
    commits = [dict(r) for r in rows]
    read_conn.close()

    print(f"{len(commits)} 件のissue参照コミットを分類します ...")

    # Phase 1: GitHub API呼び出し（DBアクセスなし）
    issue_cache: dict[tuple[str, int], str | None] = {}
    results: dict[int, int] = {}  # commit_id -> complexity
    classified = skipped = 0

    for row in tqdm(commits, desc="issue分類中"):
        commit_id = row["id"]
        message = row["commit_message"] or ""
        repo_name = row["repo"]

        refs = extract_issue_numbers(message)
        if not refs:
            results[commit_id] = 0
            skipped += 1
            continue

        complexity = 0
        for repo_override, issue_num in refs:
            effective_repo = repo_override or repo_name
            cache_key = (effective_repo, issue_num)

            if cache_key not in issue_cache:
                while True:
                    try:
                        issue_cache[cache_key] = fetch_issue_text(g, effective_repo, issue_num)
                        break
                    except RateLimitExceededException:
                        wait_for_rate_limit(g)

            issue_text = issue_cache[cache_key]
            if issue_text and is_complexity_related(issue_text):
                complexity = 1
                break

        results[commit_id] = complexity
        classified += 1

    # Phase 2: CSVに保存（DBロックの影響を受けない）
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["commit_id", "issue_complexity"])
        writer.writerows(results.items())
    print(f"CSVに保存しました: {args.out} ({len(results)} 件)")
    print(f"  難解さ関連 (1): {sum(v == 1 for v in results.values())}")
    print(f"  非該当    (0): {sum(v == 0 for v in results.values())}")

    # Phase 3: DBに反映
    print("DBに書き込み中 ...")
    _import_csv(args.out, args.db)


if __name__ == "__main__":
    main()
