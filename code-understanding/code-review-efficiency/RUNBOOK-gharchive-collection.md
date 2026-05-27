# 別PCでデータ収集を続けるための手順書

このファイルは「GitHub レビューデータ収集」を別PCで再開するための実務手順。
研究の背景・設計判断の全文脈は [STEERING-code-review-efficiency.md](STEERING-code-review-efficiency.md) を参照（特に「データ収集の設計」節）。

## いま何をしているか（1行）

レビューで **「なぜこの実装か」と聞かれ、作者が弁明し、それが受理された**箇所＝②設計根拠が「必要だったのにコードに無かった」証拠を、GitHub のレビューデータから集めている。最終的にこれを位置予測（どのコードに②を残すべきか）の正解ラベルにする。

## 全体パイプライン

- **Stage 1（アーカイブ・トークン不要・オフライン完結）** ← いまここ。手法は検証済み。
  - GH Archive の公開gzipを落として `PullRequestReviewCommentEvent` を抽出 → 「why質問×作者返信」のペア候補を作る。
- **Stage 2（要 GitHub トークン・後回し）**
  - 候補PRにだけ GraphQL を当て、`isResolved`（スレッド解決）・`isOutdated`（その行が後で変わったか＝弁明かミス修正か）・`merged` を取得し「弁明して受理（行不変）」を確定。
- **Stage 3（LLM分類）**
  - 質問が本物の設計why（criteria ii/iii）か、作者返信が rationale か（「commit見て」等で既存成果物を指すだけなら laziness として除外）を判定。

## 検証済みの実績（2026-05-27, mac側で2025-03-03の1日）

- review comment 77,028件/日 → why質問ルート 980件 → **作者返信ペア候補 385件/日**。
- 品質：ランダム6件中5件が本物の②設計根拠Q&A。ペア化が強力なノイズ除去になっている。
- 見積もり：clean正例 **約1,000件なら1週間窓（DL約22GB）、数千件なら2〜4週間**。律速はDL帯域のみ。

## 別PCでのセットアップ

```bash
git clone https://github.com/9gai/tekitou.git   # 既にあるなら git pull
cd tekitou/code-understanding/code-review-efficiency
python3 --version   # 3.8+ 想定。標準ライブラリのみ（追加pip不要）
```

`data/` は .gitignore 済みなので転送されない。別PCでは下記コマンドで落とし直す（アーカイブが一次ソースなので問題なし）。

## 実行手順

### Stage 1: 抽出

```bash
# 日付範囲(両端含む)を時間単位でDL→抽出→gz削除(resumable)
python3 collect_gharchive.py extract 2025-03-03 2025-03-09
```

- 出力：`data/gharchive/rc_YYYY-MM-DD-H.jsonl`（review commentだけのcompact行）。
- gzは解析後に削除するのでディスク常駐は小。**DL量＝1日約3GB／1週約22GB／1ヶ月約95GB**。
- 中断しても再実行で続きから（処理済み時間はskip）。
- 注意：DLには User-Agent が必須（スクリプトで設定済み。素のurllibだとCloudflareが403）。

### Stage 1: 候補作成

```bash
python3 collect_gharchive.py candidates
```

- 抽出済み全ファイルから「why質問ルート（作者以外・非bot・正規表現一致）× 作者の返信」を突き合わせる。
- 出力：`data/gharchive/candidates.jsonl`（repo, pr, path, 質問本文, 作者返信本文, author_association 等）。
- スレッドは時間をまたぐので、ペア化には数週間の連続窓が望ましい（短いと日跨ぎ返信を取りこぼす）。

## このあとやること（チェックリスト）

- [ ] 収集する窓を決める（目標 clean 正例数から逆算。まず1〜2週間が現実的）
- [ ] `extract` で収集 → `candidates` でペア生成
- [ ] **GitHub personal access token を用意**（Stage 2 の前提。未確認のまま）
- [ ] Stage 2 スクリプトを書く：candidates の各PRに GraphQL で `reviewThreads { isResolved, comments { isOutdated, author, authorAssociation, body } }` ＋ PR `merged` を取得 → 「merged ＋ thread resolved ＋ ルートが not outdated」で確定。resolvedが使えなければ「merged＋作者返信＋行不変」に緩める。
- [ ] Stage 3：LLMで「本物の設計why」「返信がrationaleか（laziness除外）」を分類（10kを並列分類した前例あり）。
- [ ] 確定した正例＝「②が必要だったのにコードに無かった箇所」を、位置予測の正解ラベルとして整備。

## 注意点（再掲）

- 人間PRに絞るなら bot/エージェント著者を除外（login の `[bot]` 等。スクリプトで一部除外済み）。
- `isOutdated`/`isResolved` は近似・運用がリポジトリによりまばら。
- 公開リポジトリのみ（OSS狙いで問題なし）。
- Pascarella bias：拾えるのは「声に出された需要」だけ＝高precision・低recall。学習正例としては許容だが主張時に断る。

## スクリプトの場所

- `collect_gharchive.py`（このディレクトリ・git管理下）。
