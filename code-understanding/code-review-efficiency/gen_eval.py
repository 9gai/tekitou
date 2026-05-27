"""Stage 3 検証用: 各シャードから positive5+negative5 を無作為抽出し
ブラインド判定HTMLと answer key を生成する.

出力(すべて data/gharchive/eval/, gitignore下):
  - answer_key.json : row_id -> {id, shard, llm_label, criteria, reason}  (答え合わせ用)
  - eval.html       : LLMラベルを伏せた判定シート(ブラウザで開く)
判定後 eval.html から judgments.json をエクスポート -> score_eval.py で照合.
"""
import json
import os
import random

HERE = os.path.dirname(__file__)
S3 = os.path.join(HERE, "data", "gharchive", "stage3")
EVAL = os.path.join(HERE, "data", "gharchive", "eval")
PER_LABEL = 5  # 各シャード positive5 + negative5
SEED = 20260527

os.makedirs(EVAL, exist_ok=True)
rng = random.Random(SEED)

# shard の Q&A を id で引けるように
def load_shard(k):
    d = {}
    for line in open(os.path.join(S3, f"shard_{k}.jsonl"), encoding="utf-8"):
        line = line.strip()
        if line:
            r = json.loads(line)
            d[str(r["id"])] = r
    return d

picked = []
for k in range(10):
    qa = load_shard(k)
    labs = [json.loads(l) for l in open(os.path.join(S3, f"labels_{k}.jsonl"), encoding="utf-8") if l.strip()]
    pos = [r for r in labs if r["label"] == "positive"]
    neg = [r for r in labs if r["label"] == "negative"]
    for grp in (pos, neg):
        rng.shuffle(grp)
        for r in grp[:PER_LABEL]:
            i = str(r["id"])
            if i not in qa:
                continue
            picked.append({
                "shard": k, "id": i, "llm_label": r["label"],
                "criteria": r.get("criteria"), "reason": r.get("reason"),
                "repo": qa[i]["repo"], "pr": qa[i]["pr"], "path": qa[i]["path"],
                "q_assoc": qa[i].get("q_assoc"), "a_assoc": qa[i].get("a_assoc"),
                "q_body": qa[i]["q_body"], "a_body": qa[i]["a_body"],
            })

rng.shuffle(picked)
for n, p in enumerate(picked, 1):
    p["row_id"] = n

# answer key (LLMラベルを含む・ブラインド対象外)
key = {str(p["row_id"]): {"id": p["id"], "shard": p["shard"],
                          "llm_label": p["llm_label"], "criteria": p["criteria"],
                          "reason": p["reason"]} for p in picked}
with open(os.path.join(EVAL, "answer_key.json"), "w", encoding="utf-8") as f:
    json.dump(key, f, ensure_ascii=False, indent=1)

# HTML 用アイテム(LLMラベルは含めない=ブラインド)
items = [{"row_id": p["row_id"], "repo": p["repo"], "pr": p["pr"], "path": p["path"],
          "q_assoc": p["q_assoc"], "a_assoc": p["a_assoc"],
          "q_body": p["q_body"], "a_body": p["a_body"]} for p in picked]

HTML = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8"><title>Stage3 検証 (ブラインド)</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:900px;margin:0 auto;padding:20px;background:#f5f5f5}
 .card{background:#fff;border:1px solid #ddd;border-radius:8px;padding:16px;margin:14px 0}
 .meta{color:#666;font-size:12px;margin-bottom:8px}
 .q{background:#eef5ff;padding:10px;border-radius:6px;margin:6px 0;white-space:pre-wrap;word-break:break-word}
 .a{background:#f0fff0;padding:10px;border-radius:6px;margin:6px 0;white-space:pre-wrap;word-break:break-word}
 .lbl{font-weight:bold;color:#333}
 .choices{margin-top:10px}
 .choices label{margin-right:18px;cursor:pointer}
 #bar{position:sticky;top:0;background:#333;color:#fff;padding:10px;border-radius:6px;z-index:10}
 button{padding:8px 16px;font-size:14px;cursor:pointer}
 textarea{width:100%;height:120px;margin-top:8px;font-family:monospace}
 .done{outline:3px solid #4caf50}
</style></head><body>
<div id="bar">進捗 <span id="prog">0</span>/<span id="tot"></span>
 &nbsp;<button onclick="exportJ()">結果をエクスポート</button>
 <span id="msg"></span></div>
<p><b>判定基準</b>: positive = (a)質問が本物の設計why「なぜこの方法か(ii)/トレードオフ(iii)」を問い、かつ
 (b)作者返信が実際にrationaleを説明している(譲歩"I'll fix"・既存成果物参照"see commit"はnegative)。両方満たせば positive。</p>
<div id="root"></div>
<div class="card"><b>エクスポート結果</b>(コピーして judgments.json として保存、または下のダウンロード)
 <div><button onclick="exportJ()">JSON生成</button>
 <button onclick="dl()">ダウンロード</button></div>
 <textarea id="out"></textarea></div>
<script>
const ITEMS = __ITEMS__;
const KEY = "stage3eval";
let J = JSON.parse(localStorage.getItem(KEY)||"{}");
const root=document.getElementById("root");
document.getElementById("tot").textContent=ITEMS.length;
function esc(s){return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
ITEMS.forEach(it=>{
 const d=document.createElement("div");d.className="card";d.id="c"+it.row_id;
 d.innerHTML=`<div class="meta">#${it.row_id} &nbsp; ${esc(it.repo)} PR${it.pr} &nbsp; ${esc(it.path)}
  &nbsp; [Q:${esc(it.q_assoc)} / A:${esc(it.a_assoc)}]</div>
  <div class="lbl">Q (reviewer):</div><div class="q">${esc(it.q_body)}</div>
  <div class="lbl">A (author):</div><div class="a">${esc(it.a_body)}</div>
  <div class="choices">
   <label><input type="radio" name="r${it.row_id}" value="positive"> positive</label>
   <label><input type="radio" name="r${it.row_id}" value="negative"> negative</label>
   <label><input type="radio" name="r${it.row_id}" value="unsure"> unsure</label></div>`;
 root.appendChild(d);
});
function refresh(){let n=0;ITEMS.forEach(it=>{const v=J[it.row_id];const c=document.getElementById("c"+it.row_id);
 if(v){n++;c.classList.add("done");const el=document.querySelector(`input[name=r${it.row_id}][value=${v}]`);if(el)el.checked=true;}
 else c.classList.remove("done");});document.getElementById("prog").textContent=n;}
root.addEventListener("change",e=>{if(e.target.name&&e.target.name[0]==="r"){
 J[e.target.name.slice(1)]=e.target.value;localStorage.setItem(KEY,JSON.stringify(J));refresh();}});
function exportJ(){document.getElementById("out").value=JSON.stringify(J,null,1);
 document.getElementById("msg").textContent="  生成しました("+Object.keys(J).length+"件)";}
function dl(){exportJ();const b=new Blob([document.getElementById("out").value],{type:"application/json"});
 const a=document.createElement("a");a.href=URL.createObjectURL(b);a.download="judgments.json";a.click();}
refresh();
</script></body></html>"""

html = HTML.replace("__ITEMS__", json.dumps(items, ensure_ascii=False))
with open(os.path.join(EVAL, "eval.html"), "w", encoding="utf-8") as f:
    f.write(html)

print(f"抽出 {len(picked)} 件 (各シャード positive{PER_LABEL}+negative{PER_LABEL})")
from collections import Counter
print("内訳(LLMラベル):", dict(Counter(p["llm_label"] for p in picked)))
print(f"-> {EVAL}/eval.html  (ブラウザで開いて判定 -> judgments.json をエクスポート)")
print(f"-> {EVAL}/answer_key.json")
