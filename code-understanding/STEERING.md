# コード理解 — 議事録・ステアリングファイル

## テーマ概要

コード理解（Program Comprehension）に関する研究・アイデアの調査・議論を記録するファイル。

---

## セッション記録

### 2026-04-15 — 第3回：Program Comprehension分野のサーベイ

→ 詳細は「Program Comprehension 分野サーベイ」セクションを参照

---

### 2026-04-15 — 第2回：コード理解の重要性の変遷調査

→ 詳細は「コード理解の重要性：以前と現在の比較」セクションを参照

---

### 2026-04-15 — 第1回：分野の全体像調査

**起点論文:**
- Hou et al., "Large Language Models for Software Engineering: A Systematic Literature Review"
  ACM TOSEM, Vol.33(8), Article 220, 2024.
  DOI: [10.1145/3695988](https://dl.acm.org/doi/10.1145/3695988) / arXiv: [2308.10620](https://arxiv.org/abs/2308.10620)
  成果物: https://github.com/xinyi-hou/LLM4SE_SLR

---

## 分野の全体像

### LLM4SE サーベイ（起点論文）の概要

2017〜2024年1月の395論文を対象とした体系的文献レビュー（SLR）。
LLMをSEタスクに応用した研究を4つのRQで整理。

| RQ | 問い |
|----|------|
| RQ1 | どのLLMアーキテクチャが使われているか |
| RQ2 | データ収集・前処理・利用方法は何か |
| RQ3 | 最適化・評価戦略は何か |
| RQ4 | どのSEタスクで成果が出ているか |

**LLMアーキテクチャの分類（RQ1）**
- Encoder-only: CodeBERT, GraphCodeBERT, UnixCoder
- Encoder-Decoder: CodeT5, PLBART
- Decoder-only: GPT系, CodeLlama, StarCoder（2023年時点で70.7%を占める）

---

## コード理解に関連するSEタスク分類（RQ4）

SE活動を6カテゴリに分け、コード理解はおもに **ソフトウェア開発** と **保守** に横断している。

### A. ソフトウェア開発
| タスク | 概要 |
|--------|------|
| Code Summarization | コードスニペットの自然言語要約を自動生成 |
| Code Comment Generation | 関数・クラス等へのコメントを自動生成 |
| Code Search | 自然言語クエリに対応するコードを検索 |
| Code Completion | 未完成コードの補完 |
| Code Understanding / Program Comprehension | コードの機能・動作の分析・解釈 |

### B. ソフトウェア品質保証
| タスク | 概要 |
|--------|------|
| Bug Detection / Localization | バグが存在する箇所の特定 |
| Vulnerability Detection | セキュリティ脆弱性の検出 |
| Code Clone Detection | 類似コード片の識別 |

### C. ソフトウェア保守
| タスク | 概要 |
|--------|------|
| Code Search（保守文脈） | 変更箇所の特定・影響範囲分析 |
| Code Change Analysis | コード変更の意味・影響の理解 |

---

## 主要モデル・ベンチマーク

### コード理解特化の事前学習モデル

| モデル | 特徴 |
|--------|------|
| CodeBERT | BERT系。コード・自然言語のdual-modal事前学習 |
| GraphCodeBERT | データフローグラフ（DFG）を組み込んだ構造理解 |
| CodeT5 | T5系エンコーダ・デコーダ。識別子情報を活用 |
| UnixCoder | AST・コメントを統合した統一表現 |
| CodeLlama / StarCoder | デコーダ専用の大規模コードLLM |

### 主要ベンチマーク

| ベンチマーク | 対象タスク |
|--------------|------------|
| CodeXGLUE | 要約・生成・翻訳・欠陥検出・クローン検出など複数タスク |
| CodeSearchNet | コード検索（6言語） |
| Defects4J / BigVul | バグ・脆弱性検出 |

---

## 研究トレンド（2023〜2024）

- **デコーダ専用LLMの台頭**: 2023年の論文の約70%がGPT系デコーダモデルを採用
- **プロンプト工学の重要化**: zero-shot / few-shot / chain-of-thought / critique の比較研究が増加
- **LLM as Evaluator**: LLMをコード要約の評価指標として使う研究が登場
- **静的解析との融合**: AST / CFG / DFG などの構造情報とLLMを組み合わせる手法
- **信頼性・堅牢性**: 過学習・データ漏洩・一般化可能性への懸念が高まる

---

## 最新動向（2025〜2026）

### 1. リポジトリスケールへの拡張（Repository-Level Understanding）
- 関数・ファイル単位からリポジトリ全体の理解へとスコープが拡大
- **SWE-Bench / SWE-Bench Pro**: 実際のGitHubイシューを解くエージェント評価が主流に
  - SWE-Bench Verified: 最高93.9%（Claude Mythos Preview）
  - SWE-Bench Pro（長時間タスク）: 最高23.3%と依然困難
- 長文脈理解（数百〜数千ファイル）とメモリ管理が新たな研究課題
- **SWE-EVO**: 長期的なコード進化シナリオのベンチマークも登場

### 2. コードエージェントの台頭
- LLMを単体で使うのではなく、**コードエージェント**（ツール使用・反復修正・実行フィードバック）として使う研究が急増
- RepairAgent（ICSE'25）等、自律的なバグ修復エージェントが登場
- エンタープライズ向けエージェント・IDEとの統合研究（LLM4Code 2026採択論文に多数）

### 3. コード推論（Code Reasoning）の深化
- **実行トレース（Execution Trace）を学習シグナルに使う**研究が登場
  - コードの実行手順を逐次シミュレートしてLLMに教える
  - "Code Execution as Grounded Supervision"（EMNLP'25）
- Chain-of-Thought の適用方法が問い直されている
  - コードを先に生成してからCoTで説明する方が有効（ICML'25）
- **CodeGlance**: LLMのコード推論の次元（静的構造 vs 動的実行）を多角分析
- 未知関数・動的実行フィーチャが小規模モデルには特に困難と判明

### 4. Code Summarization の高度化（2025）
- **プロジェクト固有の要約**（P-CodeSum）: リポジトリ内の例を活用してBLEU+5.9〜101%向上
- critque prompting が GPT-4o で最も有効と判明
- LLMの生成する要約は70〜80%のケースで人間の許容水準に届かない（Calibration研究）
- CodeLlama-Instruct 7B が実装詳細の説明でGPT-4を上回るケースあり

### 5. Code Clone Detection の進化（2025）
- **HyClone**: LLMによるスクリーニング＋動的実行検証の2段階フレームワーク
- セマンティッククローン（変数名変更・アルゴリズム置換）への対応が課題
- Llama-3.1-8B の中間層（layer 8〜15）が意味的クローン検出に有効と判明

### 6. 脆弱性検出・プログラム修復（2025）
- IDE内でのリアルタイム脆弱性検出・修復ツールの実用化（ICSE'25）
- バグ修復エージェントに木探索（MCTS）を組み込む手法（ASE'25）
- 複数のソフトウェアアーティファクト（コード・テスト・コメント）を統合したバグ局在化（TOSEM'25）

### 7. 人間とLLMの理解ギャップ研究
- LLMのperplexityが高い箇所と人間が混乱する箇所が相関することが判明
- LLM生成コードは初学者が理解しにくいという問題が浮上（ACM'25）
- LLMは意味的等価性を41%のケースで認識できない（文脈なし条件）

---

## 主要な未解決課題

- LLMの一般化可能性（ドメイン・言語・バージョン間の転移）
- 評価方法論の不統一（BLEU等の自動指標と人間評価のギャップ）
- 解釈可能性・信頼性（なぜそう理解したかの説明）
- 産業データでの検証不足（産業データ利用は全体の6研究のみ）
- **リポジトリスケールの長文脈理解**（数千ファイルのコンテキスト管理）
- **動的実行理解**（静的解析では捉えられない実行時挙動の理解）
- **LLM生成コードの可読性**（生成コードを人間が理解できるかの保証）

---

## 関連する主要会議・論文誌

| 媒体 | 概要 |
|------|------|
| ICPC (IEEE/ACM) | プログラム理解の主要国際会議（年1回）|
| TOSEM | ACM Transactions on Software Engineering and Methodology |
| ICSE / FSE / ASE | ソフトウェア工学全般のトップ会議 |

---

## 参考文献

### サーベイ・全体像
- [LLM4SE SLR (TOSEM'24)](https://dl.acm.org/doi/10.1145/3695988) — 起点論文
- [arXiv版 (最新)](https://arxiv.org/abs/2308.10620)
- [成果物リポジトリ](https://github.com/xinyi-hou/LLM4SE_SLR)
- [Deep Learning for Code Intelligence Survey (ACM'24)](https://dl.acm.org/doi/10.1145/3664597)
- [How Does LLM Reasoning Work for Code? (arXiv'25)](https://arxiv.org/html/2506.13932v1)

### Code Summarization
- [Source Code Summarization in the Era of LLMs (ICSE'25)](https://wssun.github.io/papers/2025-ICSE-LLMs4CodeSum.pdf)
- [LLM-as-a-judge for Code Summarization (arXiv'25)](https://arxiv.org/abs/2507.16587)

### リポジトリスケール・エージェント
- [SWE-Bench Pro (arXiv'25)](https://arxiv.org/pdf/2509.16941)
- [SWE-EVO (arXiv'25)](https://arxiv.org/html/2512.18470v1)
- [Awesome Repo-Level Code Generation (GitHub)](https://github.com/YerbaPage/Awesome-Repo-Level-Code-Generation)

### コード推論
- [Execution Trace Chain of Thought (OpenReview'25)](https://openreview.net/pdf?id=pFyBdPyOCQ)
- [Code Execution as Grounded Supervision (EMNLP'25)](https://aclanthology.org/2025.emnlp-main.1260.pdf)
- [CodeGlance (arXiv'26)](https://arxiv.org/html/2602.13962v1)

### バグ修復・脆弱性
- [RepairAgent (ICSE'25)](https://software-lab.org/publications/icse2025_RepairAgent.pdf)
- [LLM4APR SLR (TOSEM'26)](https://github.com/iSEngLab/AwesomeLLM4APR)

### 人間とLLMの理解比較
- [Are Humans and LLMs Confused by the Same Code? (arXiv'26)](https://www.se.cs.uni-saarland.de/publications/docs/APM+26.pdf)
- [Beginners Struggle to Understand LLM-Generated Code (ACM'25)](https://dl.acm.org/doi/pdf/10.1145/3696630.3731663)

### ワークショップ・会議
- [LLM4Code 2026 (ICSE'26 Workshop)](https://llm4code.github.io/)
- [ICPC 2024 Proceedings](https://dl.acm.org/doi/proceedings/10.1145/3643916)
- [ICPC 2025](https://conf.researchr.org/home/icpc-2025)

---

---

## Program Comprehension 分野サーベイ

### 分野の定義
人間がコードを読んで理解するプロセスを研究する分野。認知科学・HCIと接続。
主要会議：ICPC（1993年〜）

### 歴史的変遷

**1980年代：認知モデル構築期**

| モデル | 主張 |
|--------|------|
| Brooks (1983) | トップダウン：仮説を立て細分化して検証 |
| Soloway et al. (1988) | ビーコンを手がかりにプランを認識 |
| Pennington (1987) | ボトムアップ：行単位で読んで積み上げ |
| Letovsky (1986) | 状況に応じて使い分ける「日和見的処理者」 |

→ 統一モデルは今も存在しない

**1990〜2010年代：コード特性の実験期**

- 識別子命名（説明的名前 vs 略称）
- コメントの有無・質
- コード構造（深いネスト・複雑な制御フロー）
- Atoms of Confusion（演算子優先順位・三項演算子等）

主な知見：
- 説明的識別子名は欠陥発見を約14%速くする
- コメントより識別子の質の方が影響大
- Atoms of Confusionはエラー率・処理時間を増加させる

**2010年代後半〜：生理計測の台頭**

| 手法 | 何を測るか |
|------|-----------|
| 視線追跡 | 注視時間・注視回数・視線回帰 |
| EEG | 認知負荷・困惑の神経応答 |
| fMRI | コード理解中の脳活動部位 |

背景：タスク成績・アンケートでは「理解した」状態を正確に測れないという問題意識から。

**2023〜現在：LLM時代への対応**

- LLMのperplexityと人間のEEG反応の相関（ρ=0.47）が確認（2025）
- LLM生成コードは初学者に有意に読みにくいことが実証（ACM'25）
- 実験設計の問い直し："Put The Code Back In Code Comprehension Study"（ICPC'26）

### 測定手法の変遷

```
タスク成績（正解率・時間）
→ アンケート・think-aloud
→ 視線追跡（2000年代〜）
→ EEG・fMRI（2010年代後半〜）
→ LLM perplexityを人間の代理指標に（2025〜）
```

### 現在の主な未解決課題

- 統一認知モデルの不在（40年経っても合意モデルなし）
- 実験の外部妥当性（短い人工スニペットが多く実際のコードへの適用が不明）
- 評価指標の問題（タスク成績では「理解した」状態を正確に測れない）
- LLM生成コードへの対応（コード理解の対象が変わりつつある）
- 個人差の扱い（スキル・言語・経験による理解プロセスの違いが大きい）

### 主要論文
- [40 Years of Designing Code Comprehension Experiments (ACM CS'23)](https://dl.acm.org/doi/10.1145/3626522)
- [How do Humans and LLMs Process Confusing Code? (arXiv'25)](https://arxiv.org/html/2508.18547v1)
- [Atoms of Confusion on Novices (EMSE'23)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10193347/)
- [Simultaneous fMRI and Eye Tracking (ESEM'18)](https://dl.acm.org/doi/10.1145/3239235.3240495)

---

## コード理解の重要性：以前と現在の比較

### 以前の論文での捉え方（〜2023年頃）

**中心的な問い：「開発者がコードを読むコストをどう下げるか」**

- 保守コストの問題：開発者の作業時間の大半はコードを「読む・理解する」ことに費やされる
- コードへのコメント不足は産業界の一般的問題（更新されず outdated になりやすい）
- コード→自然言語の変換問題として定式化（NMT のエンコーダ・デコーダ構造を転用）
- 評価：BLEU / METEOR / ROUGE-L（参照コメントとの類似度）
- スコープ：自己完結した関数・スニペット単位

### 現在の論文での捉え方（2024〜2026年）

**中心的な問い：「LLM はコードを人間のように"推論"できるか」**

- **静的理解から動的推論へ**（CodeGlance'26）：実行時変数状態・制御フローの追跡が必要
- **リポジトリスケールへ拡張**（SWE-Bench系）：数千ファイル横断の文脈理解が問われる
- **評価指標の崩壊**（ICSE'25）：LLM の生成要約は参照要約と表現・詳細度が大きく異なり BLEU では測れない → LLM-as-evaluator へ
- **問いの逆転**（ACM'25）：LLM が生成したコードを人間が理解できるかという逆方向の問い
- **人間・LLM の混乱相関**（arXiv'26）：LLM の perplexity が高い箇所と人間が混乱する箇所が相関する

### 変化の構造

| 観点 | 以前（〜2023） | 現在（2024〜） |
|------|--------------|----------------|
| 問いの主体 | 人間の理解コストを下げたい | LLM は人間のように理解できるか |
| スコープ | 関数・スニペット単位 | リポジトリ全体・実世界タスク |
| 理解の定義 | 静的なコード→要約変換 | 動的実行推論・文脈横断理解 |
| 評価基準 | BLEU 等・参照要約との類似度 | LLM-as-evaluator・人間との比較 |
| コードの前提 | 人間が書く | LLM が生成することもある |

---

## 次回検討候補

- ( ) コード要約（Code Summarization）を深掘りする
- ( ) コード推論（Code Reasoning）と実行トレースの研究を調査
- ( ) リポジトリスケール理解（SWE-Bench系）の詳細調査
- ( ) 評価指標（BLEU代替）の最新動向
- ( ) 人間とLLMの理解ギャップ研究を深掘りする
- ( ) コード理解支援ツール・文書の個別分野を深掘りする

---

---

## 人間のコード理解支援ツール・文書の分類

### セッション記録：2026-04-17 — 第4回

### 分類体系

```
人間の理解支援
├── 静的情報
│   ├── ドキュメント（コメント・識別子名・README）
│   └── 可視化（UML・コールグラフ）
├── 動的情報
│   └── 実行トレース・デバッガ可視化
├── 開発環境（IDE）
│   ├── ナビゲーション・コード検索
│   └── コンテキスト情報提示
└── AI支援（2022〜）
    └── LLMによるコード説明・要約
```

---

### 1. ドキュメント

| 種類 | 知見 |
|------|------|
| インラインコメント | 最も研究量が多い。コメントあり→欠陥発見約14%速い |
| 識別子名 | コメントより影響大という研究あり |
| docstring / API doc | 研究は少ない。コードとの整合性が重要属性 |
| README / アーキテクチャ文書 | 保守コスト削減との関連が語られるが実験的検証は少ない |

- "A Decade of Code Comment Quality Assessment: A Systematic Literature Review" (JSS 2023) で21の品質属性が整理されているが，ほとんどの研究は4属性しか扱っていない
- コメントの自動品質評価はいまだ困難。人手評価が主流

---

### 2. コード可視化ツール

| ツール | 知見 |
|--------|------|
| コールグラフ（静的・動的） | 影響範囲分析に最もよく使われる。「情報過多問題」が課題 |
| UMLクラス図 | 静的構造理解に有効。**レイアウト品質が理解度に大きく影響** |
| CFG / DFG | LLM研究での利用が多い（GraphCodeBERT等）。人間向け評価は少ない |

- UMLはレイアウトが悪いと逆効果になる（多くのツールが認知的要因を無視）
- 大規模コードベースでは「情報過多」でかえって迷子になることが実証されている

---

### 3. IDE組み込みツール

- 開発者の作業時間の**57.6%がコード理解，23.9%がナビゲーション**（大規模フィールドスタディ，TSE）
- ナビゲーションの50%は「得られる情報が期待より少ない」，40%は「想定より手間がかかる」
- 効果が実証されたもの：
  - **TESTAXIS**（IntelliJ plugin）：テスト対象コードのコンテキスト表示→テスト修正時間13〜49%削減
  - **クラウドベース静的解析のIDE統合**（ESEC/FSE'21）：ツール利用が3倍に増加
  - **コード検索改善**（ESEC/FSE'24）：146,893件のイベント分析，利用パターンの問題点を特定

---

### 4. リテラシープログラミング・Notebook

- Jupyter Notebookはしばしば「散らかったスクラッチパッド」になり，文書化が不十分
- **Markdownセル：コードセル = 2:1** が良い実践の目安（再現性・理解しやすさと相関）
- **HeaderGen**（EMSE）：MLコードセルに自動でカテゴリヘッダを付与→ナビゲーション・理解タスクで実用性を確認

---

### 5. 実行トレース・動的解析

- 実行トレースの可視化は静的読解より理解を助けるという制御実験あり
- **Anteater**：Pythonの実行値をコンテキスト付きでインライン表示
- **JavaWiz**（ICPC'25）：プログラム状態を複数の可視化で提示
- 設計思想：コードを「記述順」ではなく「実行時系列順」で見せることが重要

---

### 6. LLMによるコード説明ツール（2023〜2026）

- **SpecEval**（2025）：LLMのコード理解評価フレームワーク。複数の制御フロー構造をまたぐ意味の統合が不十分と判明
- **GPT-3.5/4のコード理解テスト**（ICSE'24）：実行トレースは辿れるが**初学者と同様のエラーを犯す**
- GitHub Copilot Chat等のLLM説明ツールは普及しているが，説明品質の人手評価との相関は不明確

---

### 主要知見（全体）

- **ドキュメントが最も研究されているが，自動評価は未解決**
- **可視化はレイアウトや情報量の設計が決め手**（ツールの存在だけでは不十分）
- **IDEのナビゲーション失敗が多い**という実態が大規模計測で明らかになっている
- **LLMツールの評価は始まったばかり**。人間の理解にどう寄与するかの実証研究は少ない

---

### 参考文献

- [A Decade of Code Comment Quality Assessment (JSS 2023)](https://www.sciencedirect.com/science/article/pii/S0164121222001911)
- [Measuring Program Comprehension: A Large-Scale Field Study (TSE)](https://baolingfeng.github.io/papers/tsecomprehension.pdf)
- [TESTAXIS (ICSE/related)](https://conf.researchr.org/)
- [IDE Support for Cloud-Based Static Analyses (ESEC/FSE'21)](https://2021.esec-fse.org/details/fse-2021-papers/5/IDE-Support-for-Cloud-Based-Static-Analyses)
- [An Empirical Study of Code Search in Intelligent Coding Assistant (ESEC/FSE'24)](https://2024.esec-fse.org/details/fse-2024-industry/27/)
- [Enhancing Comprehension in Jupyter Notebooks (EMSE)](https://arxiv.org/pdf/2301.04419v2)
- [Let's Ask AI About Their Programs (ICSE'24)](https://conf.researchr.org/details/icse-2024/icse-2024-software-engineering-education-and-training-track/9/)
- [SpecEval (arXiv'25)](https://arxiv.org/html/2409.12866v2)
- [JavaWiz (ICPC'25)](https://conf.researchr.org/home/icpc-2025)
- [Anteater (arXiv)](https://arxiv.org/html/1907.02872v1)
