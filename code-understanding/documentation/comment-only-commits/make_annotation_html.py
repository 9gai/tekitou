"""
annotation/sample_100.csv からアノテーション用HTMLを生成する。

- issueへの参照があるコミットはGitHub APIでissue本文を取得
- issue本文（英語）を日本語に機械翻訳して表示
- ラベル（1/0/?）はブラウザのlocalStorageに自動保存
- 画面下部の「CSVに書き出す」ボタンで annotation/labeled.csv に出力可能

使用方法:
    pip install deep-translator  # 未インストールの場合
    export GITHUB_TOKEN=<token>  # issueを取得する場合（任意）
    python make_annotation_html.py [--csv annotation/sample_100.csv] [--db dataset.db]
"""

import argparse
import csv
import json
import os
import time
from pathlib import Path

from deep_translator import GoogleTranslator
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

DEFAULT_CSV = Path(__file__).parent / "annotation" / "sample_100.csv"
DEFAULT_DB  = Path(__file__).parent / "dataset.db"
OUTPUT_HTML = Path(__file__).parent / "annotation" / "annotate.html"

TRANSLATE_MAX_CHARS = 4500  # Google Translate の1リクエスト上限


def translate_ja(text: str) -> str:
    if not text or not text.strip():
        return ""
    try:
        chunks, current = [], ""
        for line in text.splitlines(keepends=True):
            if len(current) + len(line) > TRANSLATE_MAX_CHARS:
                chunks.append(current)
                current = line
            else:
                current += line
        if current:
            chunks.append(current)

        translated_parts = []
        for chunk in chunks:
            result = GoogleTranslator(source="auto", target="ja").translate(chunk)
            translated_parts.append(result or "")
            time.sleep(0.3)  # レート制限対策
        return "\n".join(translated_parts)
    except Exception as e:
        return f"[翻訳失敗: {e}]"


def fetch_issue(repo: str, issue_number: int, github_token: str) -> dict:
    try:
        from github import Github
        g = Github(github_token)
        issue = g.get_repo(repo).get_issue(issue_number)
        return {
            "number":  issue.number,
            "title":   issue.title or "",
            "body":    issue.body or "",
            "html_url": issue.html_url,
        }
    except Exception as e:
        return {"number": issue_number, "title": "", "body": f"[取得失敗: {e}]", "html_url": ""}


def load_issue_refs(db_path: Path, commit_hashes: list[str]) -> dict[str, list[tuple[str | None, int]]]:
    """DBからコミットハッシュ → issue参照のマッピングを返す。"""
    if not db_path.exists():
        return {}
    import sqlite3
    from utils.comment_detector import extract_issue_numbers
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    result: dict[str, list] = {}
    placeholders = ",".join("?" * len(commit_hashes))
    rows = conn.execute(
        f"SELECT commit_hash, commit_message, has_issue_ref FROM commits "
        f"WHERE commit_hash IN ({placeholders})",
        commit_hashes,
    ).fetchall()
    for row in rows:
        if row["has_issue_ref"]:
            refs = extract_issue_numbers(row["commit_message"] or "")
            if refs:
                result[row["commit_hash"]] = refs
    conn.close()
    return result


def build_entries(csv_path: Path, db_path: Path, github_token: str) -> list[dict]:
    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    commit_hashes = [r["github_url"].split("/commit/")[-1] for r in rows if r.get("github_url")]
    issue_refs = load_issue_refs(db_path, commit_hashes) if db_path.exists() else {}

    entries = []
    for i, row in enumerate(rows, 1):
        commit_hash = row.get("github_url", "").split("/commit/")[-1]
        repo = row.get("repo", "")

        # issue取得・翻訳
        issue_data = None
        refs = issue_refs.get(commit_hash, [])
        if refs and github_token:
            repo_override, issue_number = refs[0]
            target_repo = repo_override or repo
            print(f"  [{i:>3}] issue #{issue_number} を取得中 ({target_repo}) ...")
            raw = fetch_issue(target_repo, issue_number, github_token)
            if raw["title"] or raw["body"]:
                print(f"         翻訳中 ...")
                title_ja = translate_ja(raw["title"])
                body_ja  = translate_ja(raw["body"][:3000])  # 本文は3000字まで
                issue_data = {
                    "number":   raw["number"],
                    "html_url": raw["html_url"],
                    "title_en": raw["title"],
                    "title_ja": title_ja,
                    "body_en":  raw["body"][:3000],
                    "body_ja":  body_ja,
                }

        entries.append({
            "index":               i,
            "label":               row.get("label", ""),
            "notes":               row.get("notes", ""),
            "github_url":          row.get("github_url", ""),
            "repo":                repo,
            "commit_date":         row.get("commit_date", ""),
            "commit_message":      row.get("commit_message", ""),
            "is_different_author": row.get("is_different_author", ""),
            "time_gap_days":       row.get("time_gap_days", ""),
            "file_path":           row.get("file_path", ""),
            "target_class":        row.get("target_class", ""),
            "comment_type":        row.get("comment_type", ""),
            "added_comment":       row.get("added_comment", ""),
            "target_method":       row.get("target_method", ""),
            "issue":               issue_data,
        })

    return entries


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>アノテーション</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, sans-serif; font-size: 14px; margin: 0; background: #f5f5f5; }
  #header { position: sticky; top: 0; background: #1e1e2e; color: #cdd6f4; padding: 10px 20px;
            display: flex; align-items: center; gap: 16px; z-index: 100; }
  #header h1 { margin: 0; font-size: 16px; }
  #progress-text { font-size: 13px; opacity: .8; }
  #progress-bar { flex: 1; height: 8px; background: #313244; border-radius: 4px; overflow: hidden; }
  #progress-fill { height: 100%; background: #a6e3a1; border-radius: 4px; transition: width .3s; }
  #export-btn { margin-left: auto; background: #89b4fa; color: #1e1e2e; border: none;
                padding: 6px 14px; border-radius: 6px; cursor: pointer; font-weight: bold; }
  #export-btn:hover { background: #74c7ec; }

  .card { background: #fff; margin: 16px auto; max-width: 900px; border-radius: 10px;
          box-shadow: 0 2px 8px rgba(0,0,0,.08); overflow: hidden; }
  .card-header { background: #1e1e2e; color: #cdd6f4; padding: 10px 16px;
                 display: flex; align-items: center; gap: 10px; }
  .card-header .idx { font-size: 12px; opacity: .6; }
  .card-header .repo { font-weight: bold; font-size: 14px; }
  .card-header .date { font-size: 12px; opacity: .7; margin-left: auto; }
  .card-header a { color: #89b4fa; font-size: 12px; }

  .card-body { padding: 14px 16px; }
  .section { margin-bottom: 12px; }
  .section-label { font-size: 11px; font-weight: bold; color: #888; text-transform: uppercase;
                   letter-spacing: .05em; margin-bottom: 4px; }
  .commit-msg { background: #f0f4ff; border-left: 3px solid #89b4fa; padding: 8px 10px;
                border-radius: 0 6px 6px 0; font-size: 13px; white-space: pre-wrap; }
  pre { background: #1e1e2e; color: #cdd6f4; padding: 12px; border-radius: 6px;
        overflow-x: auto; font-size: 12px; line-height: 1.5; margin: 0; white-space: pre; }
  .added-comment { background: #d4f7d4; border-left: 3px solid #a6e3a1; padding: 8px 10px;
                   border-radius: 0 6px 6px 0; font-size: 13px; white-space: pre-wrap; font-family: monospace; }
  .meta-row { display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px; color: #555; }
  .meta-item { background: #f0f0f0; padding: 3px 8px; border-radius: 4px; }
  .meta-item.highlight { background: #fef3c7; color: #92400e; }

  .issue-box { background: #fff8f0; border: 1px solid #fde68a; border-radius: 6px; padding: 10px 12px; }
  .issue-box .issue-title { font-weight: bold; font-size: 13px; margin-bottom: 6px; }
  .issue-body { font-size: 12px; white-space: pre-wrap; max-height: 200px; overflow-y: auto;
                border-top: 1px solid #fde68a; margin-top: 6px; padding-top: 6px; }
  .lang-toggle { font-size: 11px; color: #89b4fa; cursor: pointer; margin-left: 8px; }

  .label-row { display: flex; align-items: center; gap: 10px; padding: 12px 16px;
               background: #fafafa; border-top: 1px solid #eee; }
  .label-row span { font-size: 13px; font-weight: bold; color: #444; }
  .label-btn { border: 2px solid #ddd; background: #fff; padding: 6px 18px; border-radius: 20px;
               cursor: pointer; font-size: 14px; font-weight: bold; transition: all .15s; }
  .label-btn:hover { border-color: #89b4fa; }
  .label-btn.selected-1 { background: #a6e3a1; border-color: #40a02b; color: #213c15; }
  .label-btn.selected-0 { background: #f38ba8; border-color: #d20f39; color: #4a0010; }
  .label-btn.selected-q { background: #fab387; border-color: #fe640b; color: #4a1800; }
  .notes-input { flex: 1; border: 1px solid #ddd; border-radius: 6px; padding: 6px 10px;
                 font-size: 13px; min-width: 0; }
</style>
</head>
<body>
<div id="header">
  <h1>コメントのみコミット アノテーション</h1>
  <div id="progress-text">0 / __TOTAL__ 件完了</div>
  <div id="progress-bar"><div id="progress-fill" style="width:0%"></div></div>
  <button id="export-btn" onclick="exportCSV()">CSVに書き出す</button>
</div>

<div id="cards"></div>

<script>
const ENTRIES = __ENTRIES_JSON__;
const TOTAL = ENTRIES.length;
const KEY = "annotation_v1";

function load() {
  try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch { return {}; }
}
function save(data) { localStorage.setItem(KEY, JSON.stringify(data)); }

function updateProgress() {
  const data = load();
  const done = Object.values(data).filter(v => v.label !== "").length;
  document.getElementById("progress-text").textContent = `${done} / ${TOTAL} 件完了`;
  document.getElementById("progress-fill").style.width = `${(done/TOTAL)*100}%`;
}

function setLabel(idx, val) {
  const data = load();
  if (!data[idx]) data[idx] = {label: "", notes: ""};
  data[idx].label = val;
  save(data);
  const btns = document.querySelectorAll(`#card-${idx} .label-btn`);
  btns.forEach(b => b.className = "label-btn");
  const map = {"1":"selected-1","0":"selected-0","?":"selected-q"};
  btns.forEach(b => { if (b.dataset.val === val) b.classList.add(map[val]); });
  updateProgress();
}

function setNotes(idx, val) {
  const data = load();
  if (!data[idx]) data[idx] = {label: "", notes: ""};
  data[idx].notes = val;
  save(data);
}

function toggleLang(idx, field) {
  const en = document.getElementById(`${field}-en-${idx}`);
  const ja = document.getElementById(`${field}-ja-${idx}`);
  if (!en || !ja) return;
  const showJa = en.style.display !== "none";
  en.style.display = showJa ? "none" : "";
  ja.style.display = showJa ? "" : "none";
}

function renderCards() {
  const data = load();
  const container = document.getElementById("cards");
  container.innerHTML = ENTRIES.map(e => {
    const saved = data[e.index] || {label: "", notes: ""};
    const labelMap = {"1":"selected-1","0":"selected-0","?":"selected-q"};
    function btnClass(v) { return "label-btn" + (saved.label === v ? " " + labelMap[v] : ""); }

    const diffAuthor = e.is_different_author == "1"
      ? `<span class="meta-item highlight">別著者が追加</span>` : "";
    const timeGap = e.time_gap_days
      ? `<span class="meta-item">${e.time_gap_days} 日後</span>` : "";

    const issueHtml = e.issue ? `
      <div class="section">
        <div class="section-label">
          関連 Issue #${e.issue.number}
          <a href="${e.issue.html_url}" target="_blank" style="margin-left:8px">GitHub で開く</a>
          <span class="lang-toggle" onclick="toggleLang(${e.index},'issue-title')">EN/JA</span>
        </div>
        <div class="issue-box">
          <div class="issue-title">
            <span id="issue-title-ja-${e.index}">${esc(e.issue.title_ja)}</span>
            <span id="issue-title-en-${e.index}" style="display:none">${esc(e.issue.title_en)}</span>
          </div>
          <div class="issue-body">
            <div id="issue-body-ja-${e.index}">${esc(e.issue.body_ja)}</div>
            <div id="issue-body-en-${e.index}" style="display:none">${esc(e.issue.body_en)}</div>
          </div>
        </div>
      </div>` : "";

    return `
    <div class="card" id="card-${e.index}">
      <div class="card-header">
        <span class="idx">#${e.index}</span>
        <span class="repo">${esc(e.repo)}</span>
        <span class="date">${esc(e.commit_date)}</span>
        <a href="${e.github_url}" target="_blank">diff を開く ↗</a>
      </div>
      <div class="card-body">
        <div class="section">
          <div class="section-label">コミットメッセージ</div>
          <div class="commit-msg">${esc(e.commit_message)}</div>
        </div>
        <div class="meta-row" style="margin-bottom:10px">
          <span class="meta-item">${esc(e.comment_type)}</span>
          <span class="meta-item">${esc(e.file_path)}</span>
          ${timeGap}
          ${diffAuthor}
        </div>
        ${issueHtml}
        <div class="section">
          <div class="section-label">追加されたコメント</div>
          <div class="added-comment">${esc(e.added_comment)}</div>
        </div>
        <div class="section">
          <div class="section-label">対象メソッド（${esc(e.target_class)}）</div>
          <pre>${esc(e.target_method)}</pre>
        </div>
      </div>
      <div class="label-row">
        <span>ラベル:</span>
        <button class="${btnClass("1")}" data-val="1" onclick="setLabel(${e.index},'1')">1 難解さ起因</button>
        <button class="${btnClass("0")}" data-val="0" onclick="setLabel(${e.index},'0')">0 非該当</button>
        <button class="${btnClass("?")}" data-val="?" onclick="setLabel(${e.index},'?')">? 不明</button>
        <input class="notes-input" type="text" placeholder="メモ（任意）"
               value="${esc(saved.notes)}"
               onchange="setNotes(${e.index}, this.value)">
      </div>
    </div>`;
  }).join("");
}

function esc(s) {
  return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
                      .replace(/"/g,"&quot;");
}

function exportCSV() {
  const data = load();
  const header = ["label","notes","github_url","repo","commit_date","commit_message",
                  "is_different_author","time_gap_days","file_path","target_class",
                  "comment_type","added_comment","target_method"];
  const rows = ENTRIES.map(e => {
    const saved = data[e.index] || {label:"",notes:""};
    return [saved.label, saved.notes, e.github_url, e.repo, e.commit_date,
            e.commit_message, e.is_different_author, e.time_gap_days,
            e.file_path, e.target_class, e.comment_type, e.added_comment, e.target_method]
      .map(v => `"${String(v||"").replace(/"/g,'""')}"`).join(",");
  });
  const blob = new Blob([header.join(",") + "\n" + rows.join("\n")], {type:"text/csv"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "labeled.csv";
  a.click();
}

renderCards();
updateProgress();
</script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--db",  type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    if not args.csv.exists():
        raise FileNotFoundError(f"{args.csv} が見つかりません。先に sample_for_annotation.py を実行してください。")

    github_token = os.environ.get("GITHUB_TOKEN", "")
    if not github_token:
        print("GITHUB_TOKEN が未設定のため issue の取得をスキップします。")

    print("エントリを読み込んでいます ...")
    entries = build_entries(args.csv, args.db, github_token)

    entries_json = json.dumps(entries, ensure_ascii=False, indent=None)
    html = HTML_TEMPLATE.replace("__ENTRIES_JSON__", entries_json).replace("__TOTAL__", str(len(entries)))

    OUTPUT_HTML.parent.mkdir(exist_ok=True)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"\n完了: {OUTPUT_HTML}")
    print("ブラウザで開いてアノテーションを開始してください:")
    print(f"  open {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
