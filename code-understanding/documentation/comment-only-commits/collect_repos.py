"""
GitHub APIを使ってJavaリポジトリを収集し，repos.csvに保存する。

使用方法:
    export GITHUB_TOKEN=<your_token>
    python collect_repos.py [--max-repos 500]
"""

import argparse
import csv
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from github import Github, RateLimitExceededException

load_dotenv(Path(__file__).parent / ".env")

OUTPUT = Path(__file__).parent / "repos.csv"

CRITERIA = {
    "language": "Java",
    "stars": ">=100",
    "fork": "false",
    "archived": "false",
}

MIN_CONTRIBUTORS = 5


def fetch_repos(g: Github, max_repos: int) -> list[dict]:
    query = (
        f"language:{CRITERIA['language']} "
        f"stars:{CRITERIA['stars']} "
        f"fork:{CRITERIA['fork']} "
        f"archived:{CRITERIA['archived']} "
        f"pushed:>=2020-01-01"
    )

    results = []
    repos = g.search_repositories(query=query, sort="stars", order="desc")

    for repo in repos:
        if len(results) >= max_repos:
            break
        try:
            # コントリビュータ数フィルタ（APIコール1回消費）
            contributors = repo.get_contributors(anon=False)
            count = sum(1 for _ in contributors)
            if count < MIN_CONTRIBUTORS:
                continue

            # コミット数フィルタ
            commits = repo.get_commits()
            n_commits = commits.totalCount
            if n_commits < 500:
                continue

            results.append({
                "repo": repo.full_name,
                "clone_url": repo.clone_url,
                "stars": repo.stargazers_count,
                "last_updated": repo.pushed_at.isoformat() if repo.pushed_at else "",
            })
            print(f"[{len(results):>4}] {repo.full_name} (stars={repo.stargazers_count})")

        except RateLimitExceededException:
            reset = g.get_rate_limit().core.reset
            wait = max((reset - time.time()), 0) + 5
            print(f"Rate limit exceeded. Waiting {wait:.0f}s ...")
            time.sleep(wait)

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-repos", type=int, default=500)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise EnvironmentError("GITHUB_TOKEN が設定されていません。export GITHUB_TOKEN=<token> を実行してください。")

    g = Github(token)
    repos = fetch_repos(g, args.max_repos)

    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["repo", "clone_url", "stars", "last_updated"])
        writer.writeheader()
        writer.writerows(repos)

    print(f"\n{len(repos)} リポジトリを {OUTPUT} に保存しました。")


if __name__ == "__main__":
    main()
