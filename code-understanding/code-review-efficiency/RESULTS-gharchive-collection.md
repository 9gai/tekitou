# GitHub レビューデータ収集パイプライン 実行結果

「レビューで**なぜこの実装か**と聞かれ、作者が弁明し受理された箇所」＝②設計根拠が「必要だったのにコードに無かった」証拠を、GH Archive から収集した。最終的に位置予測（どのコードに②を残すべきか）の正解ラベルにする。

- 背景・設計判断の全文脈：[STEERING-code-review-efficiency.md](STEERING-code-review-efficiency.md)（特に「データ収集の設計」「Stage 1+2 本実行の結果」節）
- 別PCでの再現手順：[RUNBOOK-gharchive-collection.md](RUNBOOK-gharchive-collection.md)

## 実行サマリー（収集窓：2025-03-03 → 2025-03-09 の連続1週間）

| 段階 | 内容 | 件数 | 残存率 |
|---|---|---|---|
| Stage 1: 抽出 | GH Archive の `PullRequestReviewCommentEvent` を抽出 | 453,806 review comment | — |
| Stage 1: ペア化 | why質問ルート（作者以外・非bot・正規表現）× 作者返信 | 2,985 候補（2,665 PR / 2,082 repo） | — |
| Stage 2: REST検証 | `merged` ＋ ルートコメントの行不変（position非null） | 2,539 accepted_unchanged | 85.1% |
| Stage 3: LLM分類 | 設計why（ii/iii）かつ作者返信がrationale（laziness除外） | **1,094 positive** | 43.1% |

**到達点：clean正例 1,094件**（当初目標「約1,000件」を達成）。

### Stage 3 正例の内訳

| criteria | 意味 | 件数 |
|---|---|---|
| (ii) のみ | なぜこの方法/実装を選んだか | 611 |
| (ii)＋(iii) | 上記＋トレードオフ明示 | 473 |
| (iii) のみ | トレードオフのみ | 10 |
| **トレードオフ明示(iii含む) 計** | | **483** |

正例サンプル（本物の②設計根拠Q&A）：
- `microsoft/vcpkg-tool`「なぜ make_generic() より良い?」→「make_generic は不要な `\\server\share` 処理をする。ここは相対パスと分かっている」
- `LeelaChessZero/lc0`「なぜハードコード?」→「新 backend API は NN topology を露出しないため、interface に leak させる必要が出る」
- `OpenLabsHQ/API`「なぜ local_session?」→「async_get_db だと anext() が要り煩雑、こちらが cleaner」

## 重要な知見（当初設計の修正）

1. **Stage 2 の「行不変」フィルタは追加の弁別力を持たなかった**（`line_outdated`＝position=null が 0 件）。Stage 1 で既に「作者が**返信した**ペア」に限定済みのため、作者が黙ってコードを直す（＝ミス修正）型は返信が無く最初から候補に入っていない。行不変判定と返信フィルタは情報が重複。実質効いたフィルタは `not_merged` 除外（12.4%）のみ。
2. 結果、**正例の選別は事実上すべて Stage 3（LLM）が担った**。
3. **isResolved（GraphQL限定）は未取得**。RESTのpositionが弁別しなかった以上「受理」の強い証拠が merged のみ。必要なら後段で GraphQL `isResolved`/`isOutdated` を足す余地。

## 信頼性の限界

- **Stage 3 のばらつき**：シャード間 positive率 31.5%〜53.1%（エージェント間の基準解釈ぶれ）。43.1% は粗い推定。精密化には二重ラベル＋人手検証セットが必要。トレードオフ明示(iii)層の方が定義が固く信頼できる。
- **Pascarella bias**：拾えるのは「声に出された需要」だけ＝高 precision・低 recall。モデルが学ぶのは「設計判断が客観的に必要な箇所」ではなく「レビュアが聞きがちな箇所」。学習正例としては許容だが主張時に断る。
- **公開リポジトリ・人間PRのみ**（bot/エージェント著者は除外）。

## 成果物

スクリプト（git管理下・このディレクトリ直下）：

| ファイル | 役割 |
|---|---|
| `collect_gharchive.py` | Stage 1：抽出（`extract`）＋ペア化（`candidates`） |
| `stage2_verify.py` | Stage 2：GitHub REST で merged＋行不変を検証 |
| `make_shards.py` | Stage 3 入力を10シャードに分割 |
| `merge_stage3.py` | Stage 3 ラベルの集計・検証・正例結合 |

データ（`data/` 配下・gitignore 済み＝非追跡。アーカイブから再生成可能）：

| ファイル | 内容 |
|---|---|
| `data/gharchive/rc_*.jsonl` | Stage 1 抽出（168時間分） |
| `data/gharchive/candidates.jsonl` | why質問×作者返信ペア 2,985件 |
| `data/gharchive/stage2.jsonl` | Stage 2 verdict 付き 2,985件 |
| `data/gharchive/stage3/shard_*.jsonl` | Stage 3 入力（accepted_unchanged 2,539件） |
| `data/gharchive/stage3/labels_*.jsonl` | Stage 3 ラベル（10シャード） |
| `data/gharchive/stage3/positives.jsonl` | **正例 1,094件**（元Q&A＋criteria＋reason） |

## 次の一手

1. **位置予測の正解ラベル整備**：positives.jsonl の discussion id → REST で `original_line`/`diff_hunk` を取得し「聞かれた行＝②を残すべき正例位置」を確定。
2. 検証セット（人手 or 二重ラベル）で Stage 3 の precision を実測し 43.1% を較正。
3. 負例（同一PR内で聞かれなかった hunk 等）の設計。
