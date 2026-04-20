"""
issue_complexity=1 のコミットのうち，#NNN が実際にはPRを指しているものを除外する。

ロジック：
  各コミットの #NNN 参照を再チェックし，
  「実際のissue かつ 難解さ関連」が1件もなければ issue_complexity=2 に降格する。

使用方法:
    python filter_prs.py [--db dataset.db]

環境変数:
    GITHUB_TOKEN: GitHub personal access token
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
from utils.db import get_connection

load_dotenv(Path(__file__).parent / ".env")

DEFAULT_DB = Path(__file__).parent / "dataset.db"


def fetch_issue_info(g: Github, repo_name: str, number: int) -> tuple[str | None, bool]:
    """
    issueの情報を取得する。
    Returns: (text, is_pr)
      text: タイトル+本文（取得失敗時はNone）
      is_pr: PRを参照している場合はTrue
    """
    try:
        repo = g.get_repo(repo_name)
        issue = repo.get_issue(number)
        is_pr = issue.pull_request is not None
        text = f"{issue.title}\n{issue.body or ''}"
        return text, is_pr
    except RateLimitExceededException:
        raise
    except GithubException:
        return None, False


def wait_for_rate_limit(g: Github) -> None:
    reset = g.get_rate_limit().core.reset
    wait = max((reset - time.time()), 0) + 5
    tqdm.write(f"  Rate limit exceeded. Waiting {wait:.0f}s ...")
    time.sleep(wait)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path,
                        default=Path(__file__).parent / "pr_filter_results.csv",
                        help="結果の保存先CSV（DBロック回避用）")
    parser.add_argument("--import-only", action="store_true",
                        help="CSVをDBにインポートするだけ")
    args = parser.parse_args()

    if args.import_only:
        _import_csv(args.out, args.db)
        return

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise EnvironmentError("GITHUB_TOKEN が設定されていません。")
    g = Github(token)

    conn = get_connection(args.db)
    rows = conn.execute(
        "SELECT c.id, c.commit_message, r.repo "
        "FROM commits c JOIN repos r ON c.repo_id = r.id "
        "WHERE c.issue_complexity = 1"
    ).fetchall()
    commits = [dict(r) for r in rows]
    conn.close()

    print(f"{len(commits)} 件の issue_complexity=1 コミットをPRフィルタします ...")

    issue_cache: dict[tuple[str, int], tuple[str | None, bool]] = {}
    results: dict[int, int] = {}  # commit_id -> new complexity (1=keep, 2=downgrade)

    for row in tqdm(commits, desc="PRフィルタ中"):
        commit_id = row["id"]
        message = row["commit_message"] or ""
        repo_name = row["repo"]

        refs = extract_issue_numbers(message)
        if not refs:
            results[commit_id] = 2  # 参照が抽出できなければ降格
            continue

        has_real_issue_complexity = False
        for repo_override, issue_num in refs:
            effective_repo = repo_override or repo_name
            cache_key = (effective_repo, issue_num)

            if cache_key not in issue_cache:
                while True:
                    try:
                        issue_cache[cache_key] = fetch_issue_info(g, effective_repo, issue_num)
                        break
                    except RateLimitExceededException:
                        wait_for_rate_limit(g)

            text, is_pr = issue_cache[cache_key]

            if is_pr:
                tqdm.write(f"  PR参照をスキップ: {effective_repo}#{issue_num}")
                continue  # PRは無視

            if text and is_complexity_related(text):
                has_real_issue_complexity = True
                break  # 1件でも本物のissueで難解さ関連があればOK

        results[commit_id] = 1 if has_real_issue_complexity else 2

    # CSV保存
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["commit_id", "issue_complexity"])
        writer.writerows(results.items())

    kept = sum(v == 1 for v in results.values())
    downgraded = sum(v == 2 for v in results.values())
    print(f"\nCSV保存: {args.out}")
    print(f"  維持 (1): {kept} 件")
    print(f"  降格 (2): {downgraded} 件")

    _import_csv(args.out, args.db)


def _import_csv(csv_path: Path, db_path: Path) -> None:
    with csv_path.open(encoding="utf-8") as f:
        rows = [(int(r["issue_complexity"]), int(r["commit_id"])) for r in csv.DictReader(f)]

    conn = get_connection(db_path)
    try:
        conn.executemany(
            "UPDATE commits SET issue_complexity = ? WHERE id = ?", rows
        )
        conn.commit()
        print(f"DB更新完了: {len(rows)} 件")
    finally:
        conn.close()

    # 更新後の分布確認
    conn = get_connection(db_path)
    counts = conn.execute(
        "SELECT issue_complexity, COUNT(*) as cnt FROM commits GROUP BY issue_complexity ORDER BY issue_complexity"
    ).fetchall()
    conn.close()
    print("\n更新後の分類:")
    labels = {None: "NULL（#なし）", 0: "0（#あり・番号抽出失敗）", 1: "1（issue紐づき・難解さ関連）", 2: "2（issue紐づき・難解さ非該当）"}
    for r in counts:
        label = labels.get(r["issue_complexity"], str(r["issue_complexity"]))
        print(f"  {label}: {r['cnt']} 件")


if __name__ == "__main__":
    main()
