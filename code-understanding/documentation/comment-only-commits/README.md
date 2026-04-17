# Comment-Only Commits データ収集

コードを変更せずコメントだけを追加するコミット（コメントのみコミット）を大規模にマイニングし，「開発者がコメントが必要と判断したコード」の特性を分析するためのデータセット構築スクリプト群。

研究の背景・設計の詳細は [spec.md](spec.md) を参照。

---

## セットアップ

```bash
pip install -r requirements.txt
export GITHUB_TOKEN=<your_github_token>
```

GitHubトークンは `collect_repos.py` のみで使用する。Personal Access Token（read権限のみで可）を [GitHub Settings](https://github.com/settings/tokens) から発行する。

---

## 実行手順

以下の順番で実行する。

### 1. リポジトリ収集

```bash
python collect_repos.py [--max-repos 500]
```

GitHub APIを使ってJavaリポジトリを検索し，`repos.csv` に保存する。

**選定基準：**
- スター数 ≥ 100
- コミット数 ≥ 500
- コントリビュータ数 ≥ 5
- 最終更新 2020年以降
- フォーク・アーカイブ済みを除外

**出力：** `repos.csv`（`repo`, `clone_url`, `stars`, `last_updated`）

---

### 2. コメントのみコミットの検出

```bash
python filter_commits.py [--repos repos.csv] [--db dataset.db] [--clone-dir /tmp/repos]
```

`repos.csv` の各リポジトリをクローンし，コードを変更せずコメントだけ追加するコミットを検出して `dataset.db` に保存する。

**コメントのみコミットの判定条件：**
- 変更ファイルがすべて `.java`
- テストファイル・自動生成ファイルを除外
- 追加行がすべてコメント行または空白行（`//`, `/*`, `*`, `*/`, `/**` で始まる行）
- コード行の削除がゼロ

クローンは処理後に自動削除される。`--clone-dir` でクローン先を変更できる（デフォルト: `/tmp/coc_repos`）。

**出力：** `dataset.db` の `repos` テーブルと `commits` テーブル

---

### 3. データ抽出

```bash
python extract_data.py [--db dataset.db]
```

`dataset.db` に保存済みのコメントのみコミットから，追加されたコメントのテキスト・対象メソッド・著者情報・時間差を抽出する。

**抽出する情報：**
- 追加されたコメントのテキストと種別（`inline` / `block` / `javadoc`）
- コメントが付いたメソッドの全テキスト・所属クラス名
- 対象コードが最初に追加されたコミットハッシュと日時
- コード導入からコメント追加までの経過日数
- 追加者と元作者が異なるか（`is_different_author`）
- コミットメッセージに明確化キーワード（`clarify`, `explain`, `confus` 等）を含むか

**注意：** 対象コードの初出コミットを追跡するためリポジトリ全履歴を走査するため，**最も時間がかかるステップ**。

**出力：** `dataset.db` の `comments` テーブル（複雑度カラムは未入力）

---

### 4. 属性付与

```bash
python annotate.py [--db dataset.db]
```

`comments` テーブルの各行に複雑度・識別子名品質を計算して書き込む。

**計算する属性：**

| 属性 | 説明 |
|------|------|
| `cyclomatic_complexity` | 循環複雑度（Lizard） |
| `loc` | メソッドの行数 |
| `parameter_count` | 引数の数 |
| `avg_identifier_length` | 平均識別子名の長さ |
| `abbrev_ratio` | 略称率（3文字以下の識別子の割合） |

---

## ファイル構成

```
comment-only-commits/
├── README.md
├── spec.md                    # 設計書
├── requirements.txt
├── collect_repos.py           # Step 1: リポジトリ収集
├── filter_commits.py          # Step 2: コメントのみコミットの検出
├── extract_data.py            # Step 3: データ抽出
├── annotate.py                # Step 4: 属性付与
├── utils/
│   ├── comment_detector.py    # Javaコメント行の判定・キーワード検出
│   └── db.py                  # SQLiteスキーマ・操作
├── repos.csv                  # Step 1の出力（gitignore対象）
└── dataset.db                 # 最終データセット（gitignore対象）
```

---

## データベーススキーマ

```
repos    リポジトリ情報
commits  コメントのみコミット一覧
comments コメント単位の詳細データ（複雑度・識別子名品質を含む）
```

詳細は [spec.md](spec.md) の「保存形式」セクションを参照。

---

## 規模感の見積もり

| 項目 | 見積もり |
|------|----------|
| 対象リポジトリ数 | 500 |
| 収集見込みサンプル数 | 10,000〜15,000件 |

Fluri et al. の知見（97%のコメント変更はコード変更と同一コミット）より，コメントのみコミットは全コミットの2〜3%程度と推定。

---

## 既知の限界

- **動機の多様性**：コードレビュー指摘・スタイルガイド準拠など，混乱以外の動機を完全には除外できない。`message_has_clarify_keyword` と `is_different_author` を組み合わせて分析時にフィルタリングすることを推奨。
- **Java限定**：他言語への一般化は別途検証が必要。
- **テストファイルの除外**：保守的に除外しているが，テストのコメントも研究対象になり得る。
