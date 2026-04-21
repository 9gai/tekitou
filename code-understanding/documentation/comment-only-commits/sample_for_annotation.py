"""
コミットメッセージキーワードフィルタの対象コミットから100件をランダムサンプリングし，
人手アノテーション用CSVを annotation/sample_100.csv に出力する。

アノテーション手順:
  1. annotation/sample_100.csv を開く
  2. 各行について以下の列を記入する:
       label  : 1 = 難解さ起因（コードが分かりにくいためコメントを追加した）
                0 = 非該当（スタイル統一・オンボーディング・レビュー形式等）
                ? = 判断できない
       notes  : 判断理由を簡潔に（任意）
  3. github_url 列のリンクで実際のコミットを確認できる

使用方法:
    python sample_for_annotation.py [--db dataset.db] [--n 100] [--seed 42]
"""

import argparse
import csv
import random
import textwrap
from pathlib import Path

from utils.db import get_connection

DEFAULT_DB = Path(__file__).parent / "dataset.db"
OUTPUT_DIR = Path(__file__).parent / "annotation"
OUTPUT_CSV = OUTPUT_DIR / "sample_100.csv"

METHOD_MAX_LINES = 40  # target_method の表示上限（長すぎると読みにくいため）


def truncate_method(text: str, max_lines: int = METHOD_MAX_LINES) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... (省略: 全{len(lines)}行)"


def build_github_url(repo: str, commit_hash: str) -> str:
    return f"https://github.com/{repo}/commit/{commit_hash}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--n", type=int, default=100, help="サンプル数")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)

    with get_connection(args.db) as conn:
        # コミットメッセージキーワードあり・未ラベルのコミットを取得
        rows = conn.execute("""
            SELECT DISTINCT
                c.id            AS commit_id,
                c.commit_hash,
                c.commit_date,
                c.commit_message,
                c.is_different_author,
                r.repo,
                cm.added_comment,
                cm.comment_type,
                cm.target_method,
                cm.target_class,
                cm.file_path,
                cm.time_gap_days
            FROM commits c
            JOIN repos r ON r.id = c.repo_id
            JOIN comments cm ON cm.commit_id = c.id
            WHERE cm.message_has_clarify_keyword = 1
              AND c.issue_complexity IS NULL
        """).fetchall()

    rows = [dict(r) for r in rows]

    # コミット単位に集約（1コミットに複数コメントがある場合は結合）
    by_commit: dict[int, dict] = {}
    for r in rows:
        cid = r["commit_id"]
        if cid not in by_commit:
            by_commit[cid] = {
                "commit_id":          cid,
                "repo":               r["repo"],
                "commit_hash":        r["commit_hash"],
                "commit_date":        r["commit_date"][:10],
                "commit_message":     r["commit_message"] or "",
                "is_different_author": r["is_different_author"],
                "time_gap_days":      r["time_gap_days"],
                "file_path":          r["file_path"],
                "target_class":       r["target_class"],
                "comment_type":       r["comment_type"],
                "added_comments":     [],
                "target_method":      r["target_method"] or "",
            }
        by_commit[cid]["added_comments"].append(r["added_comment"] or "")

    commits = list(by_commit.values())
    sample = random.sample(commits, min(args.n, len(commits)))

    OUTPUT_DIR.mkdir(exist_ok=True)

    fieldnames = [
        "label",          # アノテーション列（空欄で出力）
        "notes",          # アノテーション列（空欄で出力）
        "github_url",
        "repo",
        "commit_date",
        "commit_message",
        "is_different_author",
        "time_gap_days",
        "file_path",
        "target_class",
        "comment_type",
        "added_comment",  # 複数ある場合は "---" で区切って結合
        "target_method",
    ]

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in sample:
            writer.writerow({
                "label":               "",
                "notes":               "",
                "github_url":          build_github_url(s["repo"], s["commit_hash"]),
                "repo":                s["repo"],
                "commit_date":         s["commit_date"],
                "commit_message":      s["commit_message"],
                "is_different_author": s["is_different_author"],
                "time_gap_days":       f"{s['time_gap_days']:.1f}" if s["time_gap_days"] and s["time_gap_days"] >= 0 else "",
                "file_path":           s["file_path"],
                "target_class":        s["target_class"],
                "comment_type":        s["comment_type"],
                "added_comment":       "\n---\n".join(s["added_comments"]),
                "target_method":       truncate_method(s["target_method"]),
            })

    print(f"{len(sample)} 件を {OUTPUT_CSV} に出力しました。")
    print()
    print("【アノテーション手順】")
    print("  label 列に以下を記入してください:")
    print("    1  : 難解さ起因（コードが分かりにくいためコメントを追加した）")
    print("    0  : 非該当（スタイル統一・オンボーディング・形式的なJavadoc追加等）")
    print("    ?  : 判断できない")
    print("  github_url を開くと実際のコミット差分を確認できます。")
    print()
    print("判断の参考になる列:")
    print("  commit_message    : コメントを追加した理由のヒント")
    print("  added_comment     : 実際に追加されたコメントの内容")
    print("  is_different_author: 1 = 元作者以外が追加（強い信号）")
    print("  time_gap_days     : コード導入からの経過日数（長いほど事後的な気づき）")
    print("  target_method     : コメントが付いたコードの本体")


if __name__ == "__main__":
    main()
