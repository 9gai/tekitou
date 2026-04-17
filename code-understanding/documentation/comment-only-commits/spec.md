# Comment-Only Commits データ収集 — 設計書

## 目的

コードを変更せずコメントだけを追加するコミット（以下，コメントのみコミット）を大規模にマイニングし，「開発者がコメントが必要と判断したコード」の特性を分析するためのデータセットを構築する。

本スクリプト群はサブ研究のデータ収集フェーズに相当する。

---

## 対象言語

**Java**（理由：先行研究との比較が容易，JavaParserなど解析ツールが充実）

---

## パイプライン概要

```
1. リポジトリ収集        GitHub API → リポジトリリスト
      ↓
2. コミット列挙          PyDriller → 全コミットのdiff
      ↓
3. フィルタリング        コメントのみコミットの判定
      ↓
4. データ抽出           コメント・対象コード・メタデータ
      ↓
5. 属性付与            複雑度・識別子名品質・フラグ類
      ↓
6. 保存               SQLite
```

---

## 1. リポジトリ収集

### 選定基準

| 条件 | 値 |
|------|----|
| 言語 | Java |
| スター数 | ≥ 100 |
| コミット数 | ≥ 500 |
| コントリビュータ数 | ≥ 5 |
| 最終更新 | 2020年以降 |
| フォーク | 除外 |
| アーカイブ済み | 除外 |

### 出力

`repos.csv`：`repo_name, clone_url, stars, commits, contributors, last_updated`

---

## 2. コミットのフィルタリング

### コメントのみコミットの判定ロジック

PyDrillerで各コミットのdiffを走査し，以下の条件をすべて満たすものを対象とする：

1. **追加行がすべてコメント行または空白行**
2. **コード行の削除がゼロ**（コメント行の削除は許容）
3. **変更ファイルがすべて `.java`**

### Javaコメント行の定義

以下のいずれかで始まる行（先頭の空白を除去後）：

- `//`
- `/*`
- `*`
- `*/`
- `/**`

### 注意事項

- 文字列リテラル内の `//` を誤検出しないよう `javalang` でトークン解析する
- テストファイル（`*Test.java`, `*Tests.java`）は除外する（動機が異なる可能性）
- 自動生成ファイル（`@Generated` アノテーションを含む）は除外する

---

## 3. 抽出するデータ

### コミット単位

| フィールド | 内容 |
|-----------|------|
| `repo` | リポジトリ名 |
| `commit_hash` | コミットハッシュ |
| `commit_date` | コミット日時 |
| `commit_message` | コミットメッセージ |
| `author_id` | コメント追加者のID（匿名化ハッシュ） |

### コメント単位（1コミットに複数あり得る）

| フィールド | 内容 |
|-----------|------|
| `file_path` | 対象ファイルのパス |
| `added_comment` | 追加されたコメントのテキスト |
| `comment_type` | `inline` / `block` / `javadoc` |
| `target_method` | コメントが付いたメソッドの全テキスト |
| `target_class` | 所属クラス名 |
| `code_intro_commit` | 対象コードが最初に追加されたコミットハッシュ |
| `code_intro_date` | 対象コードの導入日時 |
| `time_gap_days` | コード導入〜コメント追加の経過日数 |
| `original_author_id` | 対象コードの元作者ID（匿名化ハッシュ） |
| `is_different_author` | 追加者 ≠ 元作者のフラグ |

---

## 4. 属性付与

### 複雑度指標（Lizardで計算）

| フィールド | 内容 |
|-----------|------|
| `cyclomatic_complexity` | 循環複雑度 |
| `cognitive_complexity` | 認知的複雑度 |
| `loc` | メソッドの行数 |
| `parameter_count` | 引数の数 |

### 識別子名品質

| フィールド | 内容 |
|-----------|------|
| `avg_identifier_length` | 平均識別子名の長さ |
| `abbrev_ratio` | 略称率（3文字以下の識別子の割合） |

### 動機フィルタリング用フラグ

| フィールド | 内容 |
|-----------|------|
| `message_has_clarify_keyword` | コミットメッセージに `clarify`, `explain`, `confus`, `document`, `tricky`, `complex` 等を含むか |
| `time_gap_days` | 長い時間差ほど事後的な気づきの可能性が高い |
| `is_different_author` | 他者によるコメント追加 → 外部から見て不明瞭という信号 |

---

## 5. 保存形式

**SQLite**（`dataset.db`）

テーブル構成：

```sql
CREATE TABLE repos (
    id INTEGER PRIMARY KEY,
    repo TEXT,
    clone_url TEXT,
    stars INTEGER,
    ...
);

CREATE TABLE commits (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER,
    commit_hash TEXT,
    commit_date TEXT,
    commit_message TEXT,
    author_id TEXT,
    FOREIGN KEY (repo_id) REFERENCES repos(id)
);

CREATE TABLE comments (
    id INTEGER PRIMARY KEY,
    commit_id INTEGER,
    file_path TEXT,
    added_comment TEXT,
    comment_type TEXT,
    target_method TEXT,
    target_class TEXT,
    code_intro_commit TEXT,
    code_intro_date TEXT,
    time_gap_days REAL,
    original_author_id TEXT,
    is_different_author INTEGER,
    cyclomatic_complexity REAL,
    cognitive_complexity REAL,
    loc INTEGER,
    parameter_count INTEGER,
    avg_identifier_length REAL,
    abbrev_ratio REAL,
    message_has_clarify_keyword INTEGER,
    FOREIGN KEY (commit_id) REFERENCES commits(id)
);
```

---

## 6. ディレクトリ構成

```
comment-only-commits/
├── spec.md              # 本設計書
├── collect_repos.py     # リポジトリ収集
├── filter_commits.py    # コメントのみコミットのフィルタリング
├── extract_data.py      # データ抽出
├── annotate.py          # 属性付与
├── utils/
│   ├── comment_detector.py   # Javaコメント行の判定
│   └── db.py                 # SQLite操作
├── repos.csv            # 収集リポジトリリスト
└── dataset.db           # 出力データセット
```

---

## 7. 規模感の見積もり

| 項目 | 見積もり |
|------|----------|
| 対象リポジトリ数 | 500 |
| 平均コミット数/リポジトリ | 1,000 |
| コメントのみコミットの割合 | 2〜3%（Fluri et al. より） |
| 収集見込みサンプル数 | 10,000〜15,000件 |

---

## 8. 既知の限界

- **動機の多様性**：コードレビュー指摘・スタイルガイド準拠など，混乱以外の動機を完全には除外できない
- **コメントのみコミットの希少性**：サンプル数は多言語対応や規模拡大で補える
- **Java限定**：他言語への一般化は別途検証が必要
- **テストコードの除外**：保守的に除外しているが，テストのコメントも研究対象になり得る

---

## 9. 使用ツール

| 用途 | ツール |
|------|--------|
| リポジトリマイニング | PyDriller |
| Java解析 | javalang |
| 複雑度計算 | Lizard |
| リポジトリ収集 | PyGithub |
| データ管理 | SQLite3（標準ライブラリ） |
