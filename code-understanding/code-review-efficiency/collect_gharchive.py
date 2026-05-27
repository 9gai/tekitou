"""GH Archive から PR review comment を抽出する Stage 1 収集スクリプト.

使い方:
  python collect_gharchive.py extract 2025-03-03 2025-03-03   # 指定日(両端含む)を時間単位で処理
  python collect_gharchive.py candidates                      # 抽出済みから why質問+作者返信の候補を作る

設計:
  - 1時間ファイル(.json.gz)を1本ずつDL → PullRequestReviewCommentEvent だけ compact 行に抽出
    → data/gharchive/rc_YYYY-MM-DD-H.jsonl に保存 → gz を削除(ディスク常駐を抑える).
  - 処理済みの時間はスキップ(resumable).
  - candidates: ルート質問(in_reply_to=None・作者以外・why系・非bot) と
    その PR 作者からの返信を突き合わせる(同一抽出窓内のみ).
"""
import gzip
import json
import os
import re
import sys
import urllib.request
from datetime import date, timedelta

BASE = "https://data.gharchive.org"
OUT_DIR = os.path.join(os.path.dirname(__file__), "data", "gharchive")
TMP_DIR = os.path.join(OUT_DIR, "_tmp")

# why系の質問パターン(粗い1次フィルタ. 最終判定は後段のLLM)
WHY_RE = re.compile(
    r"\b(why\s+not|why\s+do|why\s+did|why\s+is|why\s+are|why\s+would|why\s+use|why\s+this|"
    r"what'?s\s+the\s+reason|what\s+is\s+the\s+reason|whats\s+the\s+reason|"
    r"any\s+reason|is\s+there\s+a\s+reason|reason\s+for|reason\s+behind|"
    r"couldn'?t\s+(?:we|you)|could\s+(?:we|you)\s+just|why\s+not\s+just)\b",
    re.IGNORECASE,
)
BOT_RE = re.compile(r"(\[bot\]$|-bot$|^bot-|dependabot|renovate|codecov|greenkeeper)", re.IGNORECASE)


def hours(d0: date, d1: date):
    d = d0
    while d <= d1:
        for h in range(24):
            yield d.isoformat(), h
        d += timedelta(days=1)


def extract_one(day: str, hour: int):
    out_path = os.path.join(OUT_DIR, f"rc_{day}-{hour}.jsonl")
    if os.path.exists(out_path):
        return None  # 済み
    url = f"{BASE}/{day}-{hour}.json.gz"
    gz_path = os.path.join(TMP_DIR, f"{day}-{hour}.json.gz")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research crawler)"})
    with urllib.request.urlopen(req) as r, open(gz_path, "wb") as o:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            o.write(chunk)
    n_total = n_rc = 0
    with gzip.open(gz_path, "rt", encoding="utf-8", errors="replace") as f, \
         open(out_path, "w", encoding="utf-8") as out:
        for line in f:
            n_total += 1
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get("type") != "PullRequestReviewCommentEvent":
                continue
            p = ev.get("payload", {})
            c = p.get("comment", {})
            pr = p.get("pull_request", {})
            row = {
                "cid": c.get("id"),
                "reply_to": c.get("in_reply_to_id"),
                "user": (c.get("user") or {}).get("login"),
                "assoc": c.get("author_association"),
                "body": c.get("body"),
                "path": c.get("path"),
                "commit_id": c.get("commit_id"),
                "url": c.get("html_url"),
                "created": c.get("created_at"),
                "repo": (ev.get("repo") or {}).get("name"),
                "pr": pr.get("number"),
                "pr_author": (pr.get("user") or {}).get("login"),
                "pr_merged": pr.get("merged"),
                "pr_state": pr.get("state"),
            }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            n_rc += 1
    os.remove(gz_path)
    return n_total, n_rc


def cmd_extract(d0: str, d1: str):
    os.makedirs(TMP_DIR, exist_ok=True)
    y0 = date.fromisoformat(d0)
    y1 = date.fromisoformat(d1)
    grand_rc = 0
    for day, h in hours(y0, y1):
        try:
            res = extract_one(day, h)
        except Exception as e:
            print(f"  ! {day}-{h} 失敗: {e}", flush=True)
            continue
        if res is None:
            print(f"  = {day}-{h} 済み(skip)", flush=True)
            continue
        n_total, n_rc = res
        grand_rc += n_rc
        print(f"  + {day}-{h}: events={n_total:,} review_comments={n_rc:,} (累計RC={grand_rc:,})", flush=True)
    print(f"完了. 抽出 review_comments 累計={grand_rc:,}")


def cmd_candidates():
    # 全抽出ファイルをメモリに載せ, ルート質問と作者返信を突き合わせる
    roots = []          # why質問のルート候補
    replies_by_root = {}  # reply_to -> [返信row...]
    all_files = sorted(f for f in os.listdir(OUT_DIR) if f.startswith("rc_") and f.endswith(".jsonl"))
    n_rows = 0
    for fn in all_files:
        for line in open(os.path.join(OUT_DIR, fn), encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            n_rows += 1
            rt = r.get("reply_to")
            if rt is not None:
                replies_by_root.setdefault(rt, []).append(r)
                continue
            body = r.get("body") or ""
            user = r.get("user") or ""
            if user == r.get("pr_author"):
                continue  # 作者自身のルートコメントは需要ではない
            if BOT_RE.search(user):
                continue
            if not WHY_RE.search(body):
                continue
            roots.append(r)

    cands = []
    for root in roots:
        reps = replies_by_root.get(root["cid"], [])
        author_reps = [x for x in reps if x.get("user") == root.get("pr_author")
                       and not BOT_RE.search(x.get("user") or "")]
        if not author_reps:
            continue  # 作者の返信が(窓内に)無い
        cands.append({
            "repo": root["repo"], "pr": root["pr"], "path": root["path"],
            "q_user": root["user"], "q_assoc": root["assoc"], "q_body": root["body"],
            "q_url": root["url"], "pr_author": root["pr_author"],
            "a_body": author_reps[0]["body"], "a_assoc": author_reps[0]["assoc"],
            "n_author_replies": len(author_reps),
        })

    out = os.path.join(OUT_DIR, "candidates.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for c in cands:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"行数={n_rows:,}  why質問ルート={len(roots):,}  作者返信ペア候補={len(cands):,}")
    print(f"-> {out}")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    if len(sys.argv) >= 2 and sys.argv[1] == "extract":
        cmd_extract(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 2 and sys.argv[1] == "candidates":
        cmd_candidates()
    else:
        print(__doc__)
