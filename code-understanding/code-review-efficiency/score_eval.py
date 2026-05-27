"""Stage 3 検証: 本人判定(judgments.json) と LLMラベル(answer_key.json) を照合.

使い方:
  1. eval.html をブラウザで開き全件判定 -> 「ダウンロード」で judgments.json を取得
  2. それを data/gharchive/eval/judgments.json に置く
  3. python score_eval.py

出力: precision/recall/F1/accuracy, Cohen's κ, シャード別, 不一致ケース一覧.
正クラス=positive, gold=本人判定, 予測=LLM. unsure は集計から除外.
注意: サンプルは positive/negative を各シャード5件ずつに層化抽出しているため、
母集団(positive1094:negative1445)の率はシャード/層の重みで補正した値も併記する.
"""
import json
import os
from collections import defaultdict

HERE = os.path.dirname(__file__)
EVAL = os.path.join(HERE, "data", "gharchive", "eval")
key = json.load(open(os.path.join(EVAL, "answer_key.json"), encoding="utf-8"))
jpath = os.path.join(EVAL, "judgments.json")
if not os.path.exists(jpath):
    print(f"judgments.json が無い。eval.html で判定しエクスポートして {jpath} に置くこと。")
    raise SystemExit(1)
jud = json.load(open(jpath, encoding="utf-8"))

rows = []
n_unsure = n_missing = 0
for rid, k in key.items():
    human = jud.get(rid)
    if human is None:
        n_missing += 1
        continue
    if human == "unsure":
        n_unsure += 1
        continue
    rows.append((k["shard"], k["llm_label"], human))

tp = sum(1 for _, l, h in rows if l == "positive" and h == "positive")
fp = sum(1 for _, l, h in rows if l == "positive" and h == "negative")
fn = sum(1 for _, l, h in rows if l == "negative" and h == "positive")
tn = sum(1 for _, l, h in rows if l == "negative" and h == "negative")
n = len(rows)
prec = tp / (tp + fp) if tp + fp else 0
rec = tp / (tp + fn) if tp + fn else 0
f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
acc = (tp + tn) / n if n else 0

# Cohen's κ
po = acc
p_yes = ((tp + fp) / n) * ((tp + fn) / n)
p_no = ((fn + tn) / n) * ((fp + tn) / n)
pe = p_yes + p_no
kappa = (po - pe) / (1 - pe) if (1 - pe) else 0

print(f"判定済={n}  unsure={n_unsure}  未判定={n_missing}")
print(f"混同行列: TP={tp} FP={fp} FN={fn} TN={tn}")
print(f"precision(LLM-posの正しさ)={prec:.3f}  recall={rec:.3f}  F1={f1:.3f}  accuracy={acc:.3f}")
print(f"Cohen's kappa={kappa:.3f}")

# 母集団補正: precision はサンプル内 LLM-pos の正解率。各シャードの値を実 positive 数で重み付け。
# 実 positive 数は stage3 の labels から数える。
pos_count = defaultdict(int)
for kk in range(10):
    for line in open(os.path.join(HERE, "data", "gharchive", "stage3", f"labels_{kk}.jsonl"), encoding="utf-8"):
        line = line.strip()
        if line and json.loads(line)["label"] == "positive":
            pos_count[kk] += 1
sh_prec = {}
for sh in range(10):
    s = [(l, h) for (shd, l, h) in rows if shd == sh]
    pos = [(l, h) for (l, h) in s if l == "positive"]
    if pos:
        sh_prec[sh] = sum(1 for l, h in pos if h == "positive") / len(pos)
num = sum(sh_prec[sh] * pos_count[sh] for sh in sh_prec)
den = sum(pos_count[sh] for sh in sh_prec)
print(f"\n母集団補正 precision(シャードのpositive数で重み付け)={num/den:.3f}" if den else "")
print("シャード別 precision:", {sh: round(v, 2) for sh, v in sorted(sh_prec.items())})

print("\n--- 不一致ケース(LLM != 本人) ---")
for rid, k in key.items():
    h = jud.get(rid)
    if h and h != "unsure" and h != k["llm_label"]:
        print(f"#{rid} shard{k['shard']}: LLM={k['llm_label']} 本人={h}  criteria={k.get('criteria')}  reason={k.get('reason')}")
