"""Stage 2: 候補ペアを GitHub REST で検証し「弁明して受理(行不変)」を確定する.

使い方:
  python stage2_verify.py            # candidates.jsonl 全件を検証 -> stage2.jsonl (resumable)
  python stage2_verify.py --limit 50 # 先頭 50 PR だけ試す(動作確認用)

判定ロジック(STEERING の緩和版):
  - merged=True かつ 作者返信あり(candidates 時点で確認済) かつ
    ルートコメントの position が非null(=その行がまだ diff に存在=後で変わっていない)
    -> verdict="accepted_unchanged" (本物の②設計根拠の正例候補)
  - position=null            -> "line_outdated"  (行が変わった=ミス修正の疑い. 除外側)
  - merged=False             -> "not_merged"
  - PR/コメントが取れない     -> "unavailable"
  最終的な「本物の設計whyか/返信がrationaleか(laziness除外)」判定は Stage 3(LLM)で行う.

設計:
  - (repo, pr) 単位でグループ化し PR ごとに 2 リクエスト
    GET /repos/{o}/{r}/pulls/{n}              -> merged
    GET /repos/{o}/{r}/pulls/{n}/comments     -> 各 review comment の position を取得しルートと照合
  - X-RateLimit を見て枯渇前に reset まで待機. 403/secondary limit も待機。
  - 処理済み (repo,pr) は stage2.jsonl から読んでスキップ(resumable).
  - トークンは環境変数 GITHUB_TOKEN か同ディレクトリの .env から読む.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(__file__)
CAND = os.path.join(HERE, "data", "gharchive", "candidates.jsonl")
OUT = os.path.join(HERE, "data", "gharchive", "stage2.jsonl")
API = "https://api.github.com"
DISCUSSION_RE = re.compile(r"#discussion_r(\d+)")


def load_token():
    tok = os.environ.get("GITHUB_TOKEN", "").strip()
    if tok:
        return tok
    env = os.path.join(HERE, ".env")
    if os.path.exists(env):
        for line in open(env, encoding="utf-8"):
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "GITHUB_TOKEN":
                return v.strip().strip('"').strip("'")
    return ""


class GH:
    def __init__(self, token):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "tekitou-research",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def get(self, path, params=None):
        """REST GET. (json, status) を返す. レート制限は内部で待機."""
        url = API + path
        if params:
            url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        for attempt in range(6):
            req = urllib.request.Request(url, headers=self.headers)
            try:
                with urllib.request.urlopen(req) as r:
                    self._respect_rate(r.headers)
                    return json.loads(r.read().decode("utf-8")), 200
            except urllib.error.HTTPError as e:
                if e.code in (403, 429):  # rate / secondary limit
                    self._wait_on_limit(e.headers, attempt)
                    continue
                if e.code in (404, 451, 410):  # gone / private / DMCA
                    return None, e.code
                if e.code >= 500:
                    time.sleep(2 ** attempt)
                    continue
                return None, e.code
            except (urllib.error.URLError, TimeoutError):
                time.sleep(2 ** attempt)
        return None, -1

    def _respect_rate(self, h):
        rem = h.get("X-RateLimit-Remaining")
        reset = h.get("X-RateLimit-Reset")
        if rem is not None and reset is not None and int(rem) <= 2:
            wait = max(0, int(reset) - int(time.time())) + 2
            print(f"  …rate limit 残り{rem}. {wait}s 待機", flush=True)
            time.sleep(wait)

    def _wait_on_limit(self, h, attempt):
        retry = h.get("Retry-After")
        if retry:
            wait = int(retry) + 1
        else:
            reset = h.get("X-RateLimit-Reset")
            wait = max(0, int(reset) - int(time.time())) + 2 if reset else min(60, 2 ** attempt)
        print(f"  …403/secondary limit. {wait}s 待機", flush=True)
        time.sleep(wait)

    def pr_comments(self, owner, repo, num):
        """全 review comment を position 付きで取得(ページング)."""
        out, page = [], 1
        while True:
            data, st = self.get(
                f"/repos/{owner}/{repo}/pulls/{num}/comments",
                {"per_page": 100, "page": page},
            )
            if st != 200 or not data:
                return out, st
            out.extend(data)
            if len(data) < 100:
                return out, 200
            page += 1


def load_done():
    done = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            done.add((r["repo"], r["pr"]))
    return done


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    token = load_token()
    if not token:
        print("GITHUB_TOKEN が無い. .env に記入するか環境変数で渡すこと.")
        sys.exit(1)

    cands = [json.loads(l) for l in open(CAND, encoding="utf-8")]
    # (repo,pr) ごとに候補をまとめる(同一 PR に複数質問がありうる)
    by_pr = {}
    for c in cands:
        by_pr.setdefault((c["repo"], c["pr"]), []).append(c)

    done = load_done()
    todo = [k for k in by_pr if k not in done]
    if limit:
        todo = todo[:limit]
    print(f"PR候補={len(by_pr):,}  処理済={len(done):,}  今回処理={len(todo):,}", flush=True)

    gh = GH(token)
    counts = {}
    out_f = open(OUT, "a", encoding="utf-8")
    for i, (repo, pr) in enumerate(todo, 1):
        owner, name = repo.split("/", 1)
        pr_data, st = gh.get(f"/repos/{owner}/{name}/pulls/{pr}")
        if st != 200 or pr_data is None:
            for c in by_pr[(repo, pr)]:
                rec = dict(c, verdict="unavailable", http_status=st, merged=None, root_position=None)
                out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                counts["unavailable"] = counts.get("unavailable", 0) + 1
            out_f.flush()
            continue
        merged = bool(pr_data.get("merged"))
        comments, cst = gh.pr_comments(owner, name, pr)
        pos_by_id = {c.get("id"): c.get("position") for c in comments}

        for c in by_pr[(repo, pr)]:
            m = DISCUSSION_RE.search(c.get("q_url") or "")
            root_id = int(m.group(1)) if m else None
            found = root_id in pos_by_id
            position = pos_by_id.get(root_id)
            if not merged:
                verdict = "not_merged"
            elif not found:
                verdict = "root_not_found"  # コメント削除等
            elif position is None:
                verdict = "line_outdated"
            else:
                verdict = "accepted_unchanged"
            rec = dict(c, verdict=verdict, http_status=200, merged=merged,
                       root_found=found, root_position=position)
            out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            counts[verdict] = counts.get(verdict, 0) + 1
        out_f.flush()
        if i % 25 == 0 or i == len(todo):
            print(f"  [{i}/{len(todo)}] {repo}#{pr}  集計={counts}", flush=True)

    out_f.close()
    print(f"完了. verdict 内訳={counts}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
