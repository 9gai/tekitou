# Comment-Only Commits — 実行ログ・ステアリングファイル

設計の詳細は [spec.md](spec.md) を参照。本ファイルは実際の実行・トラブル対応・結果を記録する。

---

## 実行状況サマリー（2026-04-20時点）

| ステップ | スクリプト | 状態 | 結果 |
|---------|-----------|------|------|
| Step 1: リポジトリ収集 | `collect_repos.py` | 完了 | 500件 → `repos.csv` |
| Step 2: コメントのみコミット検出 | `filter_commits.py` | 完了 | 38,541件 → `dataset.db` |
| Step 3: データ抽出 | `extract_data.py` | 完了 | 167,996件 → `dataset.db` |
| Step 4: 属性付与 | `annotate.py` | 未実行 | — |

---

## Step 1: リポジトリ収集

- GitHub Personal Access Token を `.env` で管理（`python-dotenv` 導入）
- 500リポジトリ収集（star数 155,032〜3,850）
- 実行時間：約30分

---

## Step 2: コメントのみコミット検出

### 発生した問題と対処

**① clone_repo_to ディレクトリが事前に存在しない問題**

- 原因：PyDriller 2.6 の `clone_repo_to` は渡したディレクトリが事前に存在している必要がある
- 対処：`local_path.mkdir(parents=True, exist_ok=True)` を Repository 呼び出し前に追加

**② Windowsのパス長制限（MAX_PATH）**

- 原因：`grobidOrg/grobid` 等にファイル名が260文字を超えるファイルが含まれる
- 対処：`git config --global core.longpaths true` を実行

**③ UnicodeEncodeError（cp932）**

- 原因：Windowsの日本語エラーメッセージを `tqdm.write` が cp932 でエンコードできない
- 対処：エラー出力を `.encode("utf-8", errors="replace").decode("utf-8", errors="replace")` でサニタイズ

**④ 中断時の再開対応**

- 処理済みリポジトリをDBから取得してスキップする処理を追加

### 結果

- 500リポジトリ中 500件処理完了
- 検出コミット数：**38,541件**
- 当初見積もり（10,000〜15,000件）を大幅に上回った

---

## Step 3: データ抽出

### 初期実装の問題

旧 `get_code_origin` は対象行の起源コミットを見つけるために **全履歴を逆順スキャン** していた。
38,541コミット × 複数ファイル × 複数コメントグループ分のリモートアクセスが発生し、極めて低速だった。

### 改善①：リポジトリ単位でまとめてクローン

- 旧版：コミット1件ごとにリモートからクローン → 処理 → 削除
- 新版：リポジトリ単位でグループ化し、1回クローンして全コミットを処理後に削除

### 改善②：`get_code_origin` を `git blame` に置き換え

- 旧版：`Repository(url, to_commit=hash).traverse_commits()` で全履歴スキャン（O(N_commits)）
- 新版：`git blame -L line,line --porcelain hash^ -- file` で直接取得（O(1)相当）

さらに `git blame --porcelain` の出力にはコミットハッシュ・コミット日時・著者メールが含まれているため、
追加の `git log` 呼び出しを廃止し、**subprocess呼び出しをコメント1グループあたり3回→1回**に削減した。

### 性能比較

| バージョン | 1時間あたりの処理コメント数 | 推定総所要時間 |
|-----------|--------------------------|-------------|
| 旧版（全履歴スキャン） | 344件 | 数週間 |
| 改善①のみ | 79,491件 | 〜8時間 |
| 改善①②（最終版） | 〜96,000件以上 | 〜8時間 |

### その他の問題と対処

**PermissionError（Windowsでの一時ディレクトリ削除失敗）**
- PyDriller の内部クリーンアップ時にgitプロセスがファイルを掴んだまま削除できない
- 対処：`shutil.rmtree(local_path, ignore_errors=True)` に変更

**UnicodeEncodeError**（filter_commits.py と同様、extract_data.py にも同様の対処）

### 結果

- 167,996件のコメントを `comments` テーブルに格納
- 実行時間：約8時間

---

## Step 5: issue複雑さ分類（2026-04-20実施）

### 目的

コメントのみコミット38,541件のうち「コードの難解さに起因するもの」を絞り込む。

### 実装

`classify_issues.py`：
1. コミットメッセージから `#NNN` 形式のissue番号を抽出（`extract_issue_numbers`）
2. GitHub APIでissueのタイトル・本文を取得
3. 難解さ関連キーワード（`confus`, `unclear`, `explain`, `clarif` 等）にヒット かつ 否定シグナル（`NPE`, `crash`, `add feature` 等）がない場合に `issue_complexity=1` とする

### DBの分類スキーム

| `issue_complexity` | 意味 | 件数 |
|---|---|---|
| NULL | コミットメッセージに `#` なし（処理対象外） | 33,105 |
| 0 | `#` はあるがissue番号として抽出できない | 824 |
| 1 | issue紐づき + 難解さ関連 | 593 |
| 2 | issue紐づき + 難解さ非該当 | 4,019 |

### 実行上の問題

- `extract_data.py` が長時間実行されDBの書き込みロックを保持しており、`classify_issues.py` の書き込みが `database is locked` で繰り返し失敗した
- 対処：GitHub API呼び出しと DB書き込みをフェーズ分離し、中間結果を `issue_complexity.csv` に保存してからインポートする方式に変更

### サンプル確認で判明したノイズ

20件サンプルを目視確認した結果：

**真陽性（コードの難解さに起因）の例**
- `NationalSecurityAgency/ghidra#6498`：「`getLength()` はビット単位かバイト単位か？ドキュメントに見当たらない」
- `google/guava#2178`：「`Cache.stats()` の使い方が文書化不足。初心者には使い方が分からない」
- `google/guava#3485`：「`ImmutableList#copyOf` の null 引数での挙動を明確化してほしい」

**偽陽性の例と原因**
- `TheAlgorithms/Java#7192`, `#7284`, `#7336` 等：`#NNN` が issueではなく**PR番号**を参照しており、PRの説明文に `complex`, `document` 等が含まれていてキーワードにヒット
- `iluwatar/java-design-patterns#53`：「冗長な単語を削除」のみで難解さとは無関係

### 残存するノイズ源

1. **PR番号参照問題**：`#NNN` がissueかPRかを区別していない。GitHub APIの `issue.pull_request` 属性で判別可能
2. **TheAlgorithms型リポジトリ**：アルゴリズム実装集では「JavaDoc追加PR」が大量にあり、PR説明の `complex`/`document` キーワードが偽陽性を多数生む
3. **キーワードマッチの限界**：issueの動機がコードの難解さでも、その言葉が使われないケースは取れない

### 次のステップ候補

- [x] PR番号参照を除外するフィルタ（`issue.pull_request` で判別）→ **実施済み（`filter_prs.py`）**
- [ ] `TheAlgorithms/Java` 等の「教育目的リポジトリ」をリポジトリ種別として除外（現状6件・影響小）
- [ ] 残り247件の精度をより厳密に評価（ランダムサンプリングで手動アノテーション）

---

## Step 6: PR番号フィルタ適用結果（2026-04-20実施）

`filter_prs.py` を実装し、issue_complexity=1 の593件に対して `issue.pull_request` 属性で再確認。

| フィルタ後 | 件数 |
|---|---|
| issue_complexity=1（維持・本物のissue） | **247件** |
| issue_complexity=2（降格・PR参照だった） | 346件（降格） |

**593 → 247件**：約58%がPR参照由来の偽陽性だった。降格が多かったリポジトリ：jMonkeyEngine, jetty, sofastack, RoaringBitmap 等。

---

## Step 7: 247件のissue内容分析（2026-04-20実施）

247件に紐づく228件の固有issueを全件取得・精読し分類した（`issue_texts.csv`）。

### issueの種類別内訳（重複あり）

| カテゴリ | 件数目安 | 代表例 |
|---|---|---|
| セマンティクスが名前/型から読めない | ~60件 | `getLength()` bits or bytes？`maxConnectionsPerHost` が実際はper-URL |
| 前提条件・制約が隠れている | ~55件 | `stats()` 前に `recordStats()` 必要、`CSVFormat` がimmutable、例外が未文書 |
| APIドキュメントの誤り・古くなった記述 | ~45件 | `STATE_READY` が古い、`DateTimeFormatter` の動作と記述の乖離 |
| 設計の意図・なぜそうなっているか | ~25件 | `setValue()` が値未変更でもchangedフラグをtrueにする理由、`Mono.cache()` の並行保証 |
| APIの使い方が文書から分からない | ~25件 | `addSubscription()` にnull渡せるか、`Binding`/`Converter` のinvokeタイミング |
| 偽陽性（機能追加・バグ報告） | ~35件 | jOOQ機能追加、picocli機能要求、junit新機能 |

**実質的に「コードの難解さ」起因のissue：約210件（85%）**

### 「コメントが必要なコード」の難解さの根本原因（仮説）

1. **セマンティクスの曖昧さ**：メソッド名・戻り値型だけでは意味・単位・解釈が確定しない
2. **隠れた状態依存性**：呼び出し前後の状態、スレッドセーフ性、例外条件がAPI境界に現れない
3. **設計上の非自明な選択**：動作は読めるがなぜその実装かが不明（トレードオフ・意図的仕様）
4. **名前と動作の乖離**：メソッド名が示す契約と実際の動作が一致しない

---

## Step 8: 特徴量計算・分析（2026-04-20実施）

### 実装済みスクリプト

| スクリプト | 計算内容 |
|---|---|
| `annotate.py` | cyclomatic_complexity, loc, parameter_count, avg_identifier_length, abbrev_ratio（Lizard使用） |
| `annotate_signature.py` | is_public, return_type_primitive, method_name_word_count, throws_count（シグネチャ解析） |

**注意**：`cognitive_complexity` は `target_method` が複数メソッドを含むため正しく計算できず NULL にリセット済み。`is_different_author` と `time_gap_days` は99%以上が -1（sentinel）で使用不可。

### issue_complexity グループ別特徴量比較（target_methodありの83,962件）

| 特徴量 | NULL（#なし） | 1（高品質） | 差の方向 |
|---|---|---|---|
| cyclomatic_complexity | 2.31 | 1.46 | ↓ 低い |
| loc | 9.97 | 6.73 | ↓ 短い |
| is_public | 0.768 | **0.926** | ↑ 公開APIが多い |
| return_type_primitive | 0.401 | **0.125** | ↓ 非プリミティブが多い |
| method_name_word_count | 2.22 | 2.66 | ↑ 語数多い |
| abbrev_ratio | 0.179 | 0.073 | ↓ 略語が少ない |

### 主要な発見

1. **コメントが必要なのは公開API（92.6%がpublic）**：内部実装ではなくAPIバウンダリに集中
2. **戻り値が非プリミティブ型**：`CacheStats`・`Range`・`Duration` 等のドメイン型。意味が型から読めない
3. **構造的複雑さ（CC・LOC）は低い**：難解さの原因は構造ではなく「セマンティクスの不明確さ」

→ 従来のコード複雑度指標（CC、LOC）は「コメントが必要なコード」の識別に不十分。
　 **公開APIかつドメイン型を返すメソッドが特に説明を必要としている。**

---

## 残タスク

- [ ] 比較群（コメントが追加されなかった同条件のpublic APIメソッド）との特徴量比較
- [ ] 予測モデルの構築（現特徴量でのbaseline）

---

## 既知の注意点

- `get_code_origin_blame` は `line_no` をコメント追加後のファイルの行番号として使って blame しているため、近似的な実装になっている。正確なコード起源追跡が必要な場合は要再検討。
- Step 2 の見積もり（10,000〜15,000件）が実際の38,541件を大幅に下回った。Fluri et al. の「2〜3%」の推定よりコメントのみコミットが多い可能性がある。
