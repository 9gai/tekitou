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

- [ ] PR番号参照を除外するフィルタ（`issue.pull_request` で判別）
- [ ] `TheAlgorithms/Java` 等の「教育目的リポジトリ」をリポジトリ種別として除外
- [ ] 残り593件の精度をより厳密に評価（ランダムサンプリングで手動アノテーション）

---

## 残タスク

- [ ] Step 4: `python annotate.py --db dataset.db`
  - 各コメントに循環複雑度・LOC・識別子名品質を付与
  - Lizard でメソッド単位に計算するため、比較的高速な見込み
- [ ] Step 5 精度改善（上記「次のステップ候補」参照）

---

## 既知の注意点

- `get_code_origin_blame` は `line_no` をコメント追加後のファイルの行番号として使って blame しているため、近似的な実装になっている。正確なコード起源追跡が必要な場合は要再検討。
- Step 2 の見積もり（10,000〜15,000件）が実際の38,541件を大幅に下回った。Fluri et al. の「2〜3%」の推定よりコメントのみコミットが多い可能性がある。
