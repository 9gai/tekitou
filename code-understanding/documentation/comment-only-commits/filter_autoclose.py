"""
コメントのみコミットのうち，auto-closeキーワード（fixes/closes/resolves #NNN）で
issueを閉じたものを特定し，そのissueが実際にclosedかをGitHub APIで確認する。

処理結果はcommitsテーブルの is_autoclose・issue_closed カラムに記録する。

使用方法:
    export GITHUB_TOKEN=<token>
    python filter_autoclose.py [--db dataset.db]
"""

import argparse
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from github import Github, GithubException, RateLimitExceededException
from tqdm import tqdm

from utils.comment_detector import extract_autoclose_issues, has_autoclose_keyword
from utils.db import get_connection, initialize

load_dotenv(Path(__file__).parent / ".env")

DEFAULT_DB = Path(__file__).parent / "dataset.db"
RATE_LIMIT_WAIT = 60  # レート制限時の待機秒数


def check_issue_closed(g: Github, repo: str, issue_number: int) -> bool | None:
    """
    GitHub APIでissueのstateを確認する。
    Returns: True=closed, False=open, None=取得失敗
    """
    try:
        issue = g.get_repo(repo).get_issue(issue_number)
        return issue.state == "closed"
    except RateLimitExceededException:
        reset = g.get_rate_limit().core.reset
        wait = max((reset - time.time()), 0) + 5
        tqdm.write(f"  Rate limit exceeded. {wait:.0f}秒待機中 ...")
        time.sleep(wait)
        try:
            issue = g.get_repo(repo).get_issue(issue_number)
            return issue.state == "closed"
        except Exception:
            return None
    except GithubException as e:
        if e.status == 404:
            return None  # issueが存在しない（PRだった等）
        tqdm.write(f"  [WARN] GitHub API エラー ({repo}#{issue_number}): {e}")
        return None
    except Exception as e:
        tqdm.write(f"  [WARN] 取得失敗 ({repo}#{issue_number}): {e}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise EnvironmentError("GITHUB_TOKEN が設定されていません。")

    initialize(args.db)
    g = Github(token)

    with get_connection(args.db) as conn:
        rows = conn.execute("""
            SELECT c.id, c.commit_hash, c.commit_message, r.repo
            FROM commits c
            JOIN repos r ON r.id = c.repo_id
            WHERE c.has_issue_ref = 1
              AND c.is_autoclose IS NULL
        """).fetchall()

    print(f"{len(rows)} 件を処理します ...")

    autoclose_count = 0
    closed_count    = 0

    for row in tqdm(rows, desc="auto-close確認中"):
        commit_id      = row["id"]
        commit_message = row["commit_message"] or ""
        repo           = row["repo"]

        is_autoclose = int(has_autoclose_keyword(commit_message))

        issue_closed = None
        if is_autoclose:
            refs = extract_autoclose_issues(commit_message)
            if refs:
                repo_override, issue_number = refs[0]
                target_repo = repo_override or repo
                result = check_issue_closed(g, target_repo, issue_number)
                issue_closed = int(result) if result is not None else None
                time.sleep(0.5)  # APIレート対策

        with get_connection(args.db) as conn:
            conn.execute(
                "UPDATE commits SET is_autoclose = ?, issue_closed = ? WHERE id = ?",
                (is_autoclose, issue_closed, commit_id),
            )
            conn.commit()

        if is_autoclose:
            autoclose_count += 1
        if issue_closed == 1:
            closed_count += 1

    print(f"\n完了:")
    print(f"  auto-closeキーワードあり : {autoclose_count} 件")
    print(f"  issueが実際にclosed     : {closed_count} 件  ← 正例候補")

    # 結果サマリをDBから集計して表示
    with get_connection(args.db) as conn:
        total = conn.execute("SELECT COUNT(*) FROM commits").fetchone()[0]
        positive = conn.execute(
            "SELECT COUNT(*) FROM commits WHERE is_autoclose=1 AND issue_closed=1"
        ).fetchone()[0]

    print(f"\n全コミット数  : {total}")
    print(f"正例候補      : {positive} 件 (is_autoclose=1 AND issue_closed=1)")


if __name__ == "__main__":
    main()
