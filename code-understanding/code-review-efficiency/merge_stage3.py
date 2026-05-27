"""Stage 3 ラベルを集計・検証し、正例(positive)を元Q&Aと結合して出力."""
import json
import os
from collections import Counter

HERE = os.path.dirname(__file__)
S3 = os.path.join(HERE, "data", "gharchive", "stage3")
STAGE2 = os.path.join(HERE, "data", "gharchive", "stage2.jsonl")

# 元データ(accepted_unchanged)を id で引けるように
import re
DISC = re.compile(r"#discussion_r(\d+)")
src = {}
for line in open(STAGE2, encoding="utf-8"):
    r = json.loads(line)
    if r["verdict"] != "accepted_unchanged":
        continue
    m = DISC.search(r.get("q_url") or "")
    if m:
        src[m.group(1)] = r

# ラベル集計
labels = {}
dup = 0
for k in range(10):
    p = os.path.join(S3, f"labels_{k}.jsonl")
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        i = str(r["id"])
        if i in labels:
            dup += 1
        labels[i] = r

print(f"元 accepted_unchanged: {len(src)}")
print(f"ラベル総数: {len(labels)}  (重複id={dup})")
missing = set(src) - set(labels)
extra = set(labels) - set(src)
print(f"未ラベル: {len(missing)}  余分: {len(extra)}")

lab_c = Counter(r["label"] for r in labels.values())
dw = sum(1 for r in labels.values() if r.get("design_why"))
rr = sum(1 for r in labels.values() if r.get("reply_rationale"))
print(f"label: {dict(lab_c)}")
print(f"design_why=true: {dw}  reply_rationale=true: {rr}")
crit = Counter(tuple(sorted(r.get("criteria") or [])) for r in labels.values() if r["label"] == "positive")
print(f"positive の criteria: {dict(crit)}")

# positive を元Q&Aと結合して出力
out = os.path.join(S3, "positives.jsonl")
n = 0
with open(out, "w", encoding="utf-8") as f:
    for i, r in labels.items():
        if r["label"] != "positive" or i not in src:
            continue
        s = src[i]
        rec = {
            "id": i, "repo": s["repo"], "pr": s["pr"], "path": s["path"],
            "q_url": s["q_url"], "q_assoc": s["q_assoc"], "a_assoc": s["a_assoc"],
            "q_body": s["q_body"], "a_body": s["a_body"],
            "criteria": r.get("criteria"), "reason": r.get("reason"),
        }
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        n += 1
print(f"-> {out}  (正例 {n}件)")
