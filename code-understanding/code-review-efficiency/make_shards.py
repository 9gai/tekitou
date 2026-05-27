"""Stage 3 入力: stage2.jsonl の accepted_unchanged を id 付与し N シャードに分割."""
import json
import os
import re

HERE = os.path.dirname(__file__)
SRC = os.path.join(HERE, "data", "gharchive", "stage2.jsonl")
OUTDIR = os.path.join(HERE, "data", "gharchive", "stage3")
N = 10
DISC = re.compile(r"#discussion_r(\d+)")

os.makedirs(OUTDIR, exist_ok=True)
rows = [json.loads(l) for l in open(SRC, encoding="utf-8")]
acc = [r for r in rows if r["verdict"] == "accepted_unchanged"]

items = []
for r in acc:
    m = DISC.search(r.get("q_url") or "")
    cid = m.group(1) if m else None
    items.append({
        "id": cid,
        "repo": r["repo"], "pr": r["pr"], "path": r["path"],
        "q_assoc": r["q_assoc"], "a_assoc": r["a_assoc"],
        "q_body": r["q_body"], "a_body": r["a_body"],
    })

shards = [[] for _ in range(N)]
for i, it in enumerate(items):
    shards[i % N].append(it)

for k, sh in enumerate(shards):
    with open(os.path.join(OUTDIR, f"shard_{k}.jsonl"), "w", encoding="utf-8") as f:
        for it in sh:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

print(f"accepted_unchanged={len(acc)}  -> {N} シャード (各 ~{len(items)//N}件)")
print(f"出力: {OUTDIR}/shard_0..{N-1}.jsonl")
