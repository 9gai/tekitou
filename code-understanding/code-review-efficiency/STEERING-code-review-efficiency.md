# コードレビュー効率化 — 議事録・ステアリングファイル

## テーマ概要

**問題設定：AIが大量にコードを生成する時代に，人間のコードレビューがボトルネック化する。** この現状にどんなアプローチが可能かを最新研究から考える。generic なレビュー効率化ではなく「**AI/エージェント生成コードのレビューという固有負荷**」に焦点を当てる。
これまでの「コメントのみコミット」研究・generic効率化はいずれも一つの切り口にすぎない。

親テーマ：[STEERING-code-understanding.md](../STEERING-code-understanding.md)
関連：[../documentation/STEERING-documentation.md](../documentation/STEERING-documentation.md)（コメント研究）

### この問題が実在する証拠（実測）

- エージェント生成PRの**約70%が「レビュー長期化・未レビュー・却下」**に陥る（Hassan et al. 2025, *Agentic Software Engineering: Foundational Pillars and a Research Roadmap*, arXiv 2509.06216）
- AIレビューツールを導入しても人間のレビューは速くなっていない（業界調査：29%遅化・24%時短・47%変化なし, LeadDev）

---

## セッション記録

### 2026-05-26 — 第1回：レビュー効率化分野のサーベイ

ワークフロー：Web検索でアブストラクトを確認 → 関係ありそうな論文はPDF精読。
精読したもの：MCRサーベイ（arXiv 2405.18216）／LLMレビュー評価（arXiv 2505.20206）／変更分割の対照実験（PeerJ CS 2019）。

→ 詳細は「分野の全体像」「サブ領域別」セクションを参照。

### 2026-05-26 — 第2回：起点論文（MSR 2026）の精読

問題設定を「AI生成コード時代のレビューボトルネック」に明確化。起点論文として MSR 2026 の Haider & Zimmermann を全文精読。
→ 詳細は「起点論文：MSR 2026」セクションを参照。

---

## 研究の論点整理（2026-05-26 第3回）

### 一本の軸（research throughline）
**AIが量産するコードを，品質と人間の理解を保ったまま，許容コストでどう保証するか。**

### 固まったこと（前提・再検討不要）
1. 問題は実在：エージェントPRの約70%がボトルネック化／AIレビューツール導入でも人間は時短していない。
2. レビューには2つの目的＝**品質保証 ＋ 知識移転・共同所有**。効率化は後者を侵食しうる（deskilling・所有感喪失）。
3. AI著者だと**知識移転の半分が崩れ**，理解せず通す **rubber-stamping** のリスクが出る。
4. **メカニズムはコードレビューを継承，目的は assurance（検証・監査）へ分岐**。

### 決めるべきこと（open decisions）
- **A. 位置づけ**：新SEタスク(A) か コードレビュー内の分化(B) か → 半分は**実証で判定可能**（AIコードのレビューが人間コードと質的に違う挙動を示すか）。現状の証拠（MSR'26＝同分類だが重み違い）は(B)寄りだが対照群が無く未証明。
- **B. 参照分野の構え**：**基盤＝MCR**／**差別化レンズ＝human-automation oversight・trust calibration**（automation bias・complacency。MCRがほぼ持たない視点）／**目的の中身＝V&V・テスト**。原点の program comprehension（理解コスト）も接続。上位枠組みは Agentic SE（Hassan et al. 2025）。
- **C. 工数の測り方**：①マイニング代理指標（first-response time・time-to-merge・コメント密度・**提出後churn**・反復回数）／②制御実験（time-on-task・欠陥/偽陽性・NASA-TLX）／③生理計測（視線・EEG・IDEテレメトリ）。AIDevは①のみ可。時間は待ち時間交絡が強いので**churnとコメント密度を主指標・時間は補助**が頑健。「review effort proxy」と明記すること。
- **D. データ**：AIDev（93万PR）に乗るか，独自収集するか。
- **E. 既存資産の接続**：comment-only-commits（「説明が必要と判断された箇所」ラベル）を AIコードの **deceptive correctness** 特定／注目箇所予測に転用できるか。

### 要（linchpin）になる研究
**AI authored vs 人間 authored PR のレビュー比較研究**。これ1本で複数を同時に解決：
- 位置づけ A/B を実証判定
- AIコードのレビュー工数を初めて定量化
- MSR'26 が欠いた対照群を埋める

### まだ曖昧で詰める問い
- 「保証できた」の**成功条件**は何か（速さ？理解の維持？欠陥減？）
- **誰の何**を助けるのか（レビュア／チーム／エージェント改善）
- アウトプットは「**分析・発見**」か「**ツール・手法**」か

### 次の動きの順序（案）
1. AIDevデータの実体確認（churn/timeline/comment が取れるか）
2. Hassan et al. 2025 ロードマップ精読（研究の地図・空白把握）
3. 比較研究の設計（指標選定・AI/人間PRのマッチング方法）

---

## 起点論文：MSR 2026 "Understanding Dominant Themes in Reviewing Agentic AI-authored Code"

**著者/媒体：** Md. Asif Haider, Thomas Zimmermann（UC Irvine）, MSR 2026（査読付き, 5ページ）, arXiv 2601.19287, DOI 10.1145/3793302.3793566。replication package: Zenodo 18067241。

### 何をした研究か
エージェント生成PRに対して**レビュアが実際に何にコメントしているか**を大規模実証分析。生成能力の研究は多いが「レビュア側がどう反応するか」は未解明だった点を埋める。

### データ
**AIDev データセット**（Li, Zhang, Hassan 2025, arXiv 2507.15003）を使用。5大AIエージェント（OpenAI Codex, Devin, GitHub Copilot, Cursor, Claude Code）による **932,791 件のエージェントPR**（116,211リポジトリ / 72,189開発者）。本論文はその curated subset（>100★の2,807リポジトリ・33,596PR）からjoinして **19,450件のインラインレビューコメント / 3,177 PR** を分析。

### 手法
1. PRごとにレビューコメントを連結し **BERTopic** でトピック抽出 → 49クラスタ
2. **GPT-5** でクラスタ定義を理解・統合 → 42トピック → **12テーマカテゴリ**（Conventional Commit Spec にマッピング）
   - `feat`(機能/論理), `refactor`, `docs`, `style`, `undo`(revert/rollback), `test`, `chore`(依存/import), `secu`, `build`, `perf`, `ci`, `cmd`
3. オープンソースLLM（**Gemma 3:12B** via ollama）でゼロショット自動アノテーション

### RQ1: LLMはレビューテーマを自動分類できるか
検証セット：100PR / 571コメントを著者が手動アノテーションして比較。
- コメントレベル：Exact Match **0.7863**, macro F1 0.7756, Cohen's κ 0.7348（substantial agreement）
- PRレベル：Top-1精度 **0.78**, macro F1 0.8819, Jaccard 0.8142
→ オープンソースLLMでも実用的な精度で分類可能。

### RQ2: エージェントPRレビューで何が論点になるか（19,007コメント/3,162PR）
| テーマ | コメント割合 | PR割合 |
|---|---|---|
| feat（機能正しさ・論理・実装） | **38.5%** | **46.5%** |
| refactor（不要コード・簡素化） | 14% | 10.4% |
| docs（ドキュメント・ログ） | 11.4% | 10.5% |
| style（整形・可読性） | 10.3% | 8.5% |
| undo（revert/rollback） | 10% | 8.7% |
| test | 5.7% | 4.7% |
| chore / secu / build / perf / ci / cmd | 残り（各<3.3%） | — |

### RQ3: 承認PR vs 却下PR でテーマが違うか（Chi-Square）
- 却下=closedだがmerge無し（2,558コメント/483PR），承認=closed+merge（12,191/2,035）
- **承認PRで有意に多い**：docs（10.05%却下 vs 12.97%承認, p<0.001）, style（p<0.05）→「core logicが健全なので磨く価値がある建設的ハードル」
- **却下PRで有意に多い＝マージ阻害要因**：test（6.53% vs 5.44%, p<0.05）, secu（PR単位 5.59% vs 3.05%, p<0.01）, build（3.11% vs 1.57%, p<0.05）
- `undo`（不要なrevert）が却下PRに多い（borderline p≈0.057）＝**エージェントが無駄な変更を出しレビュアが却下**

### 結論・含意
- **docs/styleは"建設的障害"，test/secu/buildは"マージ阻害要因"**
- 「**agentic noise**（PRの目的に寄与しない無駄な変更）」がレビュア疲労を増やす
- 提言は**エージェント側**：内部検証ループ強化・人間に回す前に自己修正・失敗パターン（secu/test）でfine-tuning

### 批判的評価（研究機会）
1. **記述的・観察的研究にとどまる**：「何にコメントされるか」は分かるが「レビューが遅いか／どう速くするか」は測っていない。レビュー時間・認知負荷は未測定。
2. **人間コードとの直接比較がない**：「AIコードのレビューは人間コードと違う」と示唆するが，同一研究内に人間PRの対照群が無い → **AI vs 人間 authored PRのレビュー工数比較**は未着手の穴。
3. **提言がエージェント側に偏る**：レビュア支援ツール（どこを重点的に見るべきか提示する等）は未構築。
4. **方法論の弱さ**：却下の定義（archival等を含みうる），検証セット小（100PR/単一アノテータ），多重比較未補正でType Iリスク。
5. **AIDevデータセット（932k PR）は再利用可能な資産** → ここに乗って研究を組める。

### 自分の研究との接続
- RQ3の「マージ阻害要因（test/secu/build）」「agentic noise（undo）」は，**人間レビュー前に重点を当てるべき箇所**の候補。これを予測しレビュアに提示すれば「ボトルネック緩和」に直結。
- 既存資産「コメントのみコミット＝説明が必要と判断された箇所」のラベルは，AIコードの「**deceptive correctness（もっともらしいが危うい箇所）**」の特定に転用できる可能性。

---

## 基礎文献：Tao et al. FSE 2012 "How Do Software Engineers Understand Code Changes?"

**著者/媒体：** Yida Tao, Yingnong Dang, Tao Xie, Dongmei Zhang, Sunghun Kim。FSE 2012（Microsoft産業調査）。
**手法：** オンライン調査180名（SDE 99/SDET 56/PM 25, 平均経験9.1年）＋ フォローアップemailインタビュー。文献180本超から15の情報ニーズ候補を抽出し，重要度・取得困難度を4段階評価させた。**自己申告ベース（時間の実測ではない）**点に注意。

### 変更理解は code review で最も頻出
「他人の変更レビュー（承認/コメント）」が**最頻シナリオ（67.2%, 1位）**。変更理解は日次・1日数回発生する indispensable な実務。

### 15の情報ニーズ分類（Table 2）

**A. 変更そのものの推論・評価（Reasoning & Assessing）**
- I-1 **Rationale**：この変更の根拠（なぜ）は何か
- I-2 **Completeness**：変更は完全か。同時に直すべき箇所を見落としていないか
- I-3 **Correctness**：変更は正しいか。期待通り動くか
- I-4 **Design**：悪い設計を持ち込む/既存設計を壊すか
- I-5 **Clones**：コードクローンを生むか
- I-6 **Behavior**：動的振る舞いをどう変えるか

**B. 文脈と影響の探索（Context & Impact）**
- I-7 **References**：変更したクラス/メソッド/フィールドを誰が参照しているか
- I-8 **Caller**：呼び出し側は変更にどう適応するか
- I-9 **Risk**：この変更は**他のどこかを壊さないか**
- I-10 **Consistency**：同様の変更が必要な他箇所はないか
- I-11 **Tests**：検証にどのテストを走らせるべきか
- I-12 **New tests**：追加テストは必要か
- I-13 **Failing tests**：変更のどの部分がテスト失敗を起こしうるか

**C. 変更履歴の評価（Change History）**
- I-14 **Change-proneness**：この箇所は過去の変更ホットスポットか
- I-15 **Defect-proneness**：この箇所は過去のバグ修正ホットスポットか

### 重要度 vs 困難度（Fig 5, 6）
- **最重要（score>2）**：I-1 Rationale ＞ I-3 Correctness ＞ I-9 Risk ＞ I-4 Design ＞ I-2 Completeness
- **最も取得困難**：I-10 Consistency ＞ I-9 Risk ＞ I-2 Completeness（クローン・failing tests が続く）
- **重要かつ困難（右上＝優先課題）：I-9 Risk, I-2 Completeness, I-10 Consistency, I-3 Correctness**
- **反直感的発見**：I-1 Rationale は**最重要だが最も容易**。ただし容易さは**コミットメッセージ/変更説明の質に依存**。Buse & Weimer：コミットの67%しか変更を正確に記述していない。例「refactor code」だけだと根拠が分からず混乱。

### その他の発見
- **Risk(I-9)の現行手段**＝テスト（時間がかかる・テスト十分性依存）＋手動レビュー（労力大・誤りやすい）＋IDE静的解析（find references。ただし量が多いと圧倒され，**コンポーネント境界では"前提が文書化されていない"ため困難**）。
- **composite/tangled change**（複数の関心が1コミットに混在）は理解困難。issue単位への**分割ツールが望まれるが存在しない**。
- **履歴メトリクス(I-14, I-15)は開発者には最も非重要・容易**（彼らは"いま"を見る）。テスター/PMの方が使う可能性。

### 自分の研究への接続（※以下は未検証の仮説＝貢献余地）
Tao の15ニーズは「変更理解に何が要るか」の**検証済み測定枠組み**として転用できる。問い：**AI/エージェント著者になると、15ニーズのどれが重要度・困難度を変えるか？**
- **I-1 Rationale**：Tao は「良いコミットメッセージがあれば容易」と言う。AIエージェントは根拠を書かない/捏造する → **その条件が崩れ，人間コードでは容易だった rationale が AIコードでは困難に転じる**という仮説（Tao 2012から論理的に導けるが未実証）。comment-only-commits 資産と直結。
- **I-9 Risk / I-2 Completeness / I-10 Consistency**：人間コードで既に最難。AIは局所的にもっともらしい変更を"前提を文書化せず"行う → さらに悪化の可能性。量も効く。
- **I-3 Correctness**：deceptive correctness で困難化。
- **composite/agentic noise**：MSR'26 の undo(無駄revert)所見と符合 → 分割ニーズ上昇。
→ 「15ニーズの importance/difficulty を AI authored vs 人間 authored で比較する」研究は，(A)/(B)位置づけ判定にも「どこを速くすべきか」にも直結する具体設計。
**注意**：Tao は2012・pre-LLM・自己申告（時間実測でない）。importance/difficulty は"知覚"であって工数の実測ではない。

---

## 基礎文献：Ebert et al. SANER 2019 / EMSE 2021 "Confusion in Code Reviews"

**著者/媒体：** Felipe Ebert, Fernando Castor, Nicole Novielli, Alexander Serebrenik。SANER 2019（拡張版が EMSE 2021）。
**手法：** concurrent triangulation＝「開発者が言うこと」（調査）＋「開発者がすること」（レビューコメント分析）をグラウンデッドセオリー・カードソート・軸コーディングで統合。
- 調査：3回反復で**有効回答計54件**（1回目17件／2回目24件／3回目13件。1回目は4,645通送付で**回答率0.45%**という低さ）。回答者は経験豊富（レビュー経験>2年が80%）。
- レビューコメント：Android/Gerrit の **307件**（confusingと手動ラベル：general 156＋inline 151）。
- ※先に出た「100名/1500コメント」要約は誤り。正しくは上記。

### 混乱の頻度（重要）
**レビューする時：約41%が「半分以上の頻度で混乱」**、neverは10%のみ。**変更を書く時：混乱半分以上は12%のみ**、neverが35%。→ **混乱は"他人の変更をレビューする時"に圧倒的に多い**。

### RQ1：混乱の30の原因（4次元に整理）
**RQ1要約（論文の囲み・原文）：最も多い原因は (1) missing rationale, (2) discussion of the solution: non-functional, (3) lack of familiarity with existing code。**

- **Artifact次元（最大の原因群・11原因）**：
  - **1位＝変更の rationale の欠如**（"I do not fully understand why the code is being modified"）
  - **2位＝解の non-functional な側面の議論**（poor readability「実装が雑」, performance「転送速度が本当に変わるのか分からない」等）
  - 3位＝system behavior が不明
- **Review process次元（7原因）**：1位＝organization of work（PR説明が不明確／「レビュー準備できてる？」／「変更が複数のことをやりすぎ＝tangled」）, 2位＝ツール（rebaseで新patchset等）, 3位＝そもそも変更が必要か
- **Developer次元（6原因）**：開発者間の disagreement, 意図の誤解, 「何度も読まないと分からない」
- **Link次元（6原因）**：**既存コードへの不慣れ**（"Lack of knowledge about the code being modified"）, プログラミングスキル不足, 問題自体の理解不足

### RQ2：混乱の影響
- **マージ判断が遅延** ／ 議論メッセージ数が増加 ／ **レビュー品質が低下**
- 副次的に良い面も：より良い解の発見（批判的省察・知識移転を誘発）
- **危険な対処：混乱すると"中身を確認せず承認(blindly approve)"してしまう** ＝ rubber-stamping。AIコード文脈の核心リスクと直結。

### RQ3：対処戦略
情報を要求する ／ 既存コードへの習熟を上げる ／ オフラインで議論する ／（最悪）blindly approve。

### EMSE 2021拡張版の追加貢献（精読済み・全文）
SANER 2019（30原因・14影響・13対処）に加え，**62名の調査で最頻原因を確定**し，**解決策の系統的マッピング（427→38本）**を実施。

**最頻5原因（Scott-Knott ESD・62名）：**
1. long or complex code change（Artifact）
2. organization of work（不明確なコミットメッセージ・状態・tangled change）（Review Process）
3. dependency between different code changes
4. lack of documentation
5. **missing code change rationale**

→ **重要な再較正**：SANER 2019の「枠組み上の prevalence」では top3 が missing rationale / non-functional / 不慣れ だったが，**62名の頻度調査では non-functional は3群目に降格**。頻度で見ると non-functional は最頻ではない。**missing rationale は top5 に残る。**

**RQ5：各原因の解決策数（提案論文数）**
| 原因 | 論文数 | 解決策数 |
|---|---|---|
| long/complex | 31 | 5（短く・salient files・ツール改善・super reviews・順序付け） |
| organization of work | 8 | 2（変更を記述・composite分割） |
| lack of documentation | 5 | 2 |
| dependency | 4 | 3 |
| **missing rationale** | **3** | **1（"変更の動機を書く"のみ, MacLeod 2018）** |

→ **RQ5要約（原文）："We found only one solution proposed in the literature for missing code change rationale."** ＝最頻原因の中で**最も手薄＝最大ギャップ**。

**RQ6：missing rationale の影響＝frustration 1つのみ**（long/complex と org-of-work は遅延・品質低下・工数増・却下と多数紐づく）。

**研究アジェンダ（6.4・原文の含意）：**
> 「最も手薄な原因（organization of work, dependency, **missing rationale**, lack of documentation）にもっと投資すべき。missing rationale は（我々の調査で）混乱の最多原因なのに文献ではめったに扱われない。**コードコメントやソースコード要素から変更のrationaleを自動抽出するアプローチを作るべき。**」
> さらに：salient files の活用，**task context（LaToza 2006）**＝変更ファイル＋実装時にアクセスしたファイルをdiffと共に提示してナビゲーションを減らす，も提案。

### 自分の研究への接続（強い裏付け）
- **Ebert et al. が研究アジェンダで「コードコメント/ソース要素から rationale を自動抽出せよ」と名指しで推奨** ＝ [[project-research-goal]] の comment-only-commits 資産の方向そのもの。しかも「最頻原因なのに解決策1つだけ＝ギャップ」と実証付きで主張している。引用すれば動機づけが一次資料で固まる。
- 「whyの3層」との関係：Ebert の missing rationale ＝ ①動機寄り（コミットメッセージで埋まる層）。ただし「コードコメント/ソースから抽出」という提案は②設計根拠にも踏み込む余地。
- **較正**：当初注目した non-functional は「頻度」では最頻でない。速さ／ボトルネックを頻度で正当化するなら **missing rationale + long/complex + organization of work** が本命。
- 関連で要チェック：**Pascarella et al. 2018『Information Needs in Contemporary Code Review』**（レビュアの7情報ニーズ：代替案の妥当性・変更の正しい理解・rationale・文脈）。Tao 2012 と並ぶ情報ニーズ一次文献。

### （SANER 2019時点の記録・上記で較正済み）
- 「混乱はレビュー時>>authoring時」「混乱→遅延・品質低下・rubber-stamp（blindly approve）」は，**速さをゴールにする根拠**になる（混乱＝速さの敵）。

---

## 基礎文献：Pascarella et al. CSCW/PACMHCI 2018 "Information Needs in Contemporary Code Review"

**著者/媒体：** Luca Pascarella, Davide Spadini, Fabio Palomba, Magiel Bruntink, Alberto Bacchelli。CSCW 2018（Best of CSCW 2018に選出）。
**手法：** Gerritの **900レビュースレッド**（OpenStack/Android/Qt 各300、レビュアの質問「?」から始まるもの）を card sort（4名）で分類 → **7つの high-level 情報ニーズ・18サブカテゴリ**（Krippendorff α=98%）。加えて開発者4名インタビュー＋品質コンサル3名の focus group で検証。
（注：WebFetch要約は分類が捏造だったため，保存PDFを直接精読して作成。）

### 7つの情報ニーズ（Fig 3・頻度はFig 4の総数の目安）
1. **N1. Suitability of an alternative solution（代替案は妥当か）** — **約420件で圧倒的最多**。「もっと良いやり方はないか／別の方法では？」。サブ：suggest/ask changes, request actions。
2. **N2. Correct understanding（自分の理解は正しいか）** — 約190件。解釈の確認・疑問の明確化。コメント/ドキュメントが無いと増える。
3. **N3. Rationale（なぜ）** — 約105件。「なぜこの変更が必要か／なぜこの実装にしたか」。サブ：missing information, justifications。
4. **N4. Code context** — 約57件。文脈・挙動の明確化。
5. **N5. Necessity（本当に要るか/消せるか）** / **N6. Specialized expertise（他の専門家を呼ぶ）** / **N7. Splittable（分割すべきか）** — いずれも少数。N7が最少。

### 主要な発見
- **最頻ニーズは N1「代替案は妥当か」で他を圧倒**。＝レビュアは「これがベストの方法か／もっと良い手はないか」の判断に最も労力を割く。著者は「代替案の実用性に just-in-time でフィードバックするツールが最も有用」と示唆。
- 2位 N2「正しく理解したか」＝Bacchelli & Bird の "code review is understandability" を裏づけ。
- **N3 Rationale は3位だが"pretty popular"**。実装選択の動機に関する詳細情報が必要。
- **すべてのニーズの回答は中央値7時間で返る**（RQ2.2）→ 自動化できれば大きな時間節約の余地（＝速さに直結）。
- RQ2.1：約18%のスレッドは回答が付かない。N6（specialized expertise）が最も議論を呼ぶ。
- インタビューの含意：rationale把握はまず commit message を読む（P1「それで十分なはず」）。**だがコミットが "Yes, fix these things" 程度だと「なぜ？バグ報告は？」と聞く必要が出る＝説明不足**。新規参加者・初心者で起きやすい。文脈/rationale取得に IRC/email/Slack など Gerrit 外も使う。

### 3つの情報ニーズ論文の関係（Tao / Ebert / Pascarella）
測っている軸が違うので結論が一見ずれる：
- **Tao 2012**：rationale は最も**重要**な情報ニーズ（ただし良い説明があれば容易）。最難は Risk/Completeness/Consistency。
- **Ebert 2019/2021**：missing rationale は**最頻の混乱原因**だが解決策ほぼ無し。
- **Pascarella 2018**：レビュアが最も**頻繁に問う**のは N1「代替案は妥当か」，次に N2「正しく理解したか」，N3 rationale は3位。
→ 「頻繁に問う ≠ 重要 ≠ 困難」。reviewerは「もっと良い手は？」を頻繁に問うが，最も困る/重要なのは rationale。

### 自分の研究への接続（重要）
- **N1（代替案は妥当か）と N3（rationale）は地続き**：「この方法がベストか」を判断するには「なぜこの方法を選んだか（②設計根拠）」が要る。**最頻ニーズ N1 の裏にも②設計根拠がある**。
- AIコードでは「なぜこの方法を選んだか」が回収不能 → **N1の判断（最頻ニーズ）が特に難しくなる**仮説。rationale研究の射程が N3 だけでなく N1 にも広がる＝インパクトが大きい。
- 注意（方法論）：Pascarella は「?」で始まる**レビュアが声に出した質問**からニーズを抽出。黙って解決した/気づかなかったニーズは入らない＝「頻度」に bias がある。

---

## design rationale 文献サーベイ（2026-05-27, サブエージェント調査）

### ① rationale はどこに書かれ／なぜ失われるか（capture problem）
- **Dutoit et al. 2006『Rationale Management in SE』(Springer)** — 「capture problem」の定型：rationale は **vaporize（蒸発）** する。書く人の労力が下流の保守者にしか効かない incentive mismatch が原因。
- **Burge & Brown 2008** — argumentation ベースの rationale 捕捉（issue/alternative/argument/decision）。捕捉は高コストで続かない。
- **Tang et al.（JSS/IST 2006–2009）** — architect は rationale を文書化せず「knowledge vaporization」。
- **AlSafwan & Servant（ESEC/FSE 2019）/ AlSafwan et al.（JSS 2022）** — commit rationale を**15要素に分解**。開発者は rationale を必要とするのに見つけられず，**探すのを諦める**要因を特定。

### ② recover / extract / generate
- **Alkadhi et al.（MSR 2017 / ICSE-SEIP 2018）** — **chat/IRC** から rationale を ML 抽出（〜0.76P/0.79R）。rationale はメッセージの約25%に出現。
- **DRMiner（ASE 2024, 査読付き）** — **Jira issue ログ**から prompt-tuned LLM で latent な design rationale を抽出。+20–24% F1。抽出 rationale が自動プログラム修復を改善。
- **commit message 生成（Jiang ASE 2017 ほか）** — diff から生成するが**"what" であって "why" ではない**と明記。rationale gap は未解決。
- LLM で ADR 風 rationale を直接生成（arXiv 2025・査読前）。

### ③ rationale × code review
- **Bacchelli & Bird（ICSE 2013）** — レビューの本質は「**design rationale の articulation**」。レビューは rationale の **capture opportunity** だが，保持・回収は支援されていない。→ **12年以上 operationalize されていない**。
- **Widyasari et al.（TOSEM 2024）『Explaining Explanations』** — レビューコメントの**46%は解決策のみで説明なし**。7分類。ChatGPT が要求された説明型を 88/90 で生成。

### ④ AI生成コードの rationale / explanation
- **Wang, Mozannar et al.（FAccT 2024, 査読付き）** — **why-explanation（理由・目的）と what-explanation を区別**。why の方が適切な trust と受容を高める。ただし対象は**コードを書かせた本人**で，下流レビュアではない。
- 他は arXiv 中心（mental model, trust dynamics 等）＝査読が薄い open space。

### 決定的な発見（懸念の解消）
サブエージェントの総括：
- **(a) レビュア向けの rationale 生成**は実質未着手。既存は chat/issue からの抽出か commit message（"what"止まり）。「著者/AIの "なぜこの方法か" を回収してレビュー画面に出す」ループは誰もやっていない。Bacchelli の「レビュー＝capture機会」は12年放置。
- **(b) AI生成コードの rationale**：trust研究(FAccT 2024)は why-explanation の有効性を示すが「書かせた本人」向けで，下流レビュアの durable artifact としては未着手。**そして決定的に：AI agent は自分の deliberation（reasoning trace/plan）にアクセスできる → 人間の capture problem（蒸発）と違い，AIの rationale 捕捉は uniquely tractable**。

→ これは「AIコードに②設計根拠は存在するのか／生成は fabrication では」という懸念を**部分的に解消**する：**post-hoc にコードから再構築する(a)路線は confabulation/文脈依存の壁に当たるが，生成時に agent の deliberation を捕捉する(b)路線なら，蒸発前の本物の rationale を残せる**。人間より AI の方が捕捉しやすい，という逆転がカギ。

---

## 方針決定：実証は GitHub/AIDev で行う（2026-05-27）

- **AIコードのレビューという現象は GitHub にしか存在しない**（AI agent は GitHub に PR を出す。AIDev=GitHub）。Gerrit ベースの古典（Pascarella/Ebert/Tao）は**概念（情報ニーズ分類等）の借用に留め，実証データは GitHub/AIDev** を使う。
- トレードオフ：GitHub の PR レビューは Gerrit より構造が緩く採掘の手間が大きい（古典が Gerrit を選んだ理由がこれ）。だが AIコードでは GitHub 一択なので**関連性を優先**して手間を引き受ける。
- 本人の違和感（「現代のこの種の研究で GitHub を使わないのは変」）が起点。妥当な指摘として採用。

## 関連調査メモ（2026-05-26）

### コミットメッセージの「why」は①動機のことであって②設計根拠ではない（2026-05-27 精読で確定）
**Zeng et al.『Evaluating Generated Commit Messages with LLMs』(ICSE 2026)** を精読して，「whyは未解決」vs「高精度では」の食い違いが解けた。

- この論文は**生成ではなく評価**の論文（LLMを commit message の評価器として使い，人間と Spearman .78（Why次元）で一致する評価器を作った）。「生成でwhyが解決した」論文ではない。
- 彼らの **Why の定義** ＝「How well the commit message explains the rationale behind making the change」＝**変更を行った理由・目的（機能的な purpose）**。Li et al.[24]/Tian et al.[41] の "Rationality（コード変更への論理的説明）" に基づく。
- 例が決定的：reference「Added hash_create option **so hashes can create new threads**」＝**機能的な目的（①動機）**。「なぜAでなくBという実装にしたか（②設計根拠・トレードオフ）」ではない。
- → **整理**：コミットメッセージ研究の「why」＝**①動機/目的**。LLMはこれを生成も評価もできるようになりつつある（あなたの「高精度」の記憶は①について正しい）。一方 **②設計根拠（why-this-approach）は，この最新のICSE 2026研究でも扱っていない**（私の「未解決」は②について正しい）。
- **研究上の含意（重要）**：論文で②を主張する時，必ず「commit message研究のwhy（=①機能的目的）」と「我々の②設計根拠」を明示的に区別する必要がある。さもないと「commitのwhyはもう解けている」と却下される。逆に，この区別自体が我々の貢献の輪郭を鋭くする。
- 副産物：この評価器（commit の why 品質を人間と .78 で一致して判定）は，後で「生成した rationale の質」評価に転用できる可能性。
- 関連で生成側：ICSE 2025（ICL生成），CoMRAT（arXiv 2506.10986, commit rationale 分析）等も①目的が中心。

### non-functional / 設計根拠へのアプローチ（暫定）
- **『A Survey of Tool Support for Working with Design Decisions in Code』（ACM CSUR 2023, LaToza et al.）** — コード中の設計判断・rationaleへのツール支援のサーベイ。要精読の候補。
- NFR-aware なコード**生成**側：RobuNFR（arXiv 2503.22851），NFR自動生成（arXiv 2503.15248）。
- **暫定所見：設計判断/rationale や NFR の研究は存在するが，それを"コードレビューの理解を速くする"ために回収・提示する研究は手薄に見える＝ギャップ候補。要・追加調査で確認。**

---

## 分野の全体像

### 起点サーベイ（2つ）

- **"A Survey on Modern Code Review: Progresses, Challenges and Opportunities"** (arXiv 2405.18216, 2024)
  - MCR研究327本を体系化。改善技術 46.8%（153本）／理解研究 53.2%（174本）。
- **MCR-Survey** (watreyoung, GitHub) — 2013〜2025のMCR論文をタスク分類で継続収集。論文探索の入り口。

### 結論サマリー

レビュー効率化は6サブ領域に分かれる。**実証的に効率改善（時間・遅延削減）が裏付けられているのはレビュア推薦と変更優先順位付けのみ。** 広く推奨される変更分割や近年盛り上がるLLM自動レビューは，効率（時間短縮）への効果が実証されていない／むしろ検証コストを増やすという批判的知見がある。

---

## サブ領域別の主要論文と評価

### ① レビュア推薦（効率効果が最も明確）

「誰がレビューすべきか」の自動割当。**割当ミスはマージ承認を12日遅らせる**実証があり効率に直結。

- Xia et al. *"Who should review this change?"* (ICSE 2015) — 古典（テキスト＋ファイル位置）
- **Rigby et al. *"Improving Code Reviewer Recommendation: Accuracy, Latency, Workload, and Bystanders"* (ICSE 2023)** — Meta実環境A/Bテスト。workload考慮の再ランクで負担減，ランダム割当でレイテンシ有意減。産業エビデンスとして最強。
- Rong et al. ハイパーグラフ法 (TSE 2022)

### ② 変更の優先順位付け

レビュー待ち行列をどの順で捌くか。

- Fan et al. マージ予測でタスク優先 (2018)
- **Yang et al. *"Prioritizing code review requests to improve review efficiency: a simulation study"* (2025)** — 離散事象シミュでRandom Forestがルールベースを有意に上回る。

### ③ 変更分割（推奨されるが効率効果は否定的 ← 重要）

絡み合った変更（tangled change）を概念単位に分割。

- Tao & Kim *"Partitioning composite code changes"* (ICSE 2015)
- **di Biase et al. 対照実験 (PeerJ CS 2019, 28名)** — 精読結果：
  - 偽陽性：0.42 → 0.07（**有意 p=0.03, Cliff's δ=0.36 中程度**）
  - 欠陥検出数：1.42 → 1.21（有意差なし p=0.60）
  - レビュー時間：853秒 → 802秒（**有意差なし p=0.66**）
  - 理解度：有意差なし
  - → 「分割すべき」はベストプラクティスだが **"速くなる"証拠はない**。測定ギャップ。

### ④ 変更理解の支援（可視化・文脈化）

diffだけでは分からない文脈を補い，認知負荷を削減。**コメント研究と直結する領域。**

- Wang et al. 多視点可視化 (ICSE 2017)
- **Unterkalmsteiner et al. *"Help me to understand this commit!"* (2024)** — 文脈化レビューのビジョン論文。

### ⑤ 自動レビューコメント生成（DL→LLM，最も活発だが効果未実証）

- Li et al. **CodeReviewer** (ICSE 2022) — CodeT5ベース，品質推定・コメント生成・リファイン統合。基準モデル。
- Lu et al. **LLaMA-Reviewer** (ESEC/FSE 2023)
- **"Evaluating LLMs for Code Review" (arXiv 2025)** — 精読：GPT-4o正答率68.5%，正しいコードを壊す**回帰率最大24.8%**。「完全自動は不可」「人間レビュー時間を減らす実証は提供していない」と明記。

### ⑥ 欠陥/注目行の予測

レビュアの注意をどこへ向けるか。

- **Hong et al. *"Where should I look at?"* (ICSE 2022)** — レビュアが見るべき行を推薦（行レベル局所化）。

---

## 批判的総括 ＝ 研究機会

サーベイが挙げる核心ギャップ：

1. **メトリクスの乖離**：precision/recall は測るが，**実際のレビュー時間短縮・認知コストを測った研究がほぼ無い**。変更分割もLLMレビューも「効率改善」は仮定で未実証。
2. **検証オーバーヘッドのパラドックス**（Cihan et al. 2025; Alami et al. 2025）：AIレビューが**かえって検証の手間を増やす**可能性。
3. **文脈欠如**：LLMがプロジェクト固有の履歴・設計制約を見ずに孤立動作。

### 自分の研究との接続

「コメントのみコミット＝説明が必要だった箇所」のラベルは，④変更理解支援・⑥注目行予測と接続できる。
→ 「**どの箇所に説明・文脈を足せばレビューの理解コストが下がるか**」を，AIの精度ではなく**人間のレビュー時間・認知負荷で測る**実証研究に変換できる（ここが空白領域）。

---

## 現在地のまとめ（2026-05-26 時点）

これまでの議論で，研究の方向がかなり絞れた。流れは以下。

1. 出発点：comment-only-commits（「どのコードに説明が必要か」）。
2. 方向転換：真の目的は **コードレビューの効率化**。さらに鋭く **「AIが大量にコードを生成する時代に，人間のレビューがボトルネックになる」問題** へ。
3. ゴール＝**速さ**。ただし速さの測定は難しい（代理指標 vs 被験者実験）。**待ち時間は対象外**にしたので，測るのは「実際にレビューしている間の認知負荷」＝原則 被験者実験 寄り。
4. レビューの詰まりどころ＝**変更の理解**，とくに **「なぜこう変更したか（rationale）」**。
5. rationale は3層：**①動機**（コミットメッセージで埋まる・生成技術で解決されつつある）／**②設計根拠**（なぜこの方法か・どこにも書かれない・難所）／**③正当化**（正しい/壊れないと言える理由）。狙うのは②③。
6. 一次資料での裏づけ：
   - **Tao 2012**：rationale は最重要の情報ニーズ。ただし良い変更説明があれば容易。最難は Risk / Completeness / Consistency。
   - **Ebert 2019/2021**：**missing rationale は最頻の混乱原因の1つ，なのに文献の解決策は実質1つだけ**＝最大ギャップ。著者自身が「**コード/コメントから rationale を自動抽出する研究をすべき**」と提案＝こちらの comment 資産の方向。
   - 較正：当初注目した non-functional は「頻度」では上位でない → 本命は **missing rationale + long/complex + organization of work**。
7. AIコードで②設計根拠がどう違うか（人間コードより回収が難しいのか，等）は**未確定の論点**。「作者に聞けない」「②が存在しない」といった断定はしない（本人が"変"と判断）。AIコードとの関係は実証で確かめる対象に留める。

## 実証分析①：②はレビューで実際に聞かれているか（2026-05-27）

**問い**：②設計判断（選択肢＋トレードオフ）がコードレビューで実際に発生しているか（AIに限らない一般のレビュー）。

**データ**：CodeReviewer データセット（Li et al. ICSE 2022, GitHub PR のインラインレビューコメント）の Comment_Generation。全138,227件（train 117,739 / valid 10,319 / test 10,169）から **seed=42 で1万件**サンプリング。`comment`＝レビュアのインラインコメント。データは `data/`（gitignore 済み）。

**方法**：1万件を10シャードに分け、**10エージェントを並列**で判定。基準：(i)別実装の提示／(ii)なぜこの方法か／(iii)トレードオフ言及 のいずれかで②。ラベルは `data/sample/labels_*.jsonl` に保存（id・label・criteria・tradeoff_explicit・reason）。

**結果（10,000件）**：
| 指標 | 件数 | 割合 |
|---|---|---|
| ②（design rationale 全体） | 4,348 | **43.5%** |
| (i) 代替案の提示 | 3,689 | 36.9% |
| (ii) なぜこの方法か | 612 | 6.1% |
| (iii) トレードオフ言及 | 1,365 | 13.7% |
| tradeoff_explicit | 1,059 | 10.6% |

**解釈**：
- **②が聞かれる状況は確実に・頻繁に発生**。レビューコメントの約4割が実装の選び方に関与。
- ただし大半は **(i)「別のやり方の提案」＝浅い②**。**深い②（なぜこの方法か(ii)6%・トレードオフ明示 10.6%）は約1割**。「代替案の提示」は豊富だが「明示的なトレードオフ議論」は希少。

**注意（信頼性）**：
1. **シャード間で 31.7%〜55.9% とばらつき大** ＝ エージェント間で基準(i)（"実装を変える提案"）の解釈がぶれた。43.5% は粗い推定で、精密値ではない。
2. このデータは**フィルタ済み**（コメントが付くべき変更に限定）→ 出現率は**生の GitHub PR より高め**に出ている。
3. 精密な率を出すなら：基準(i)の厳格化／二重ラベル付け／人手による検証セットが必要。tradeoff_explicit（10.6%）の方が定義が固く信頼できる。

**代表例（深い②）**：
- 「why findAll here instead of find? ... I assumed find would be marginally faster, but just curious.」(ii,iii)
- 「`in` is O(1) for Set but O(n) for List」(i,iii)
- 「Object.create is a performance bottleneck ... just use `{}` instead.」(i,iii)
- 「using delegates will add overhead ... invoking delegates is slower than calling a method directly」(i,iii)
- 「Mixing seconds and milliseconds seems dangerous ... Why not just force all to millis?」(i,iii)

**結論**：研究の前提「②はレビューで聞かれる」は**支持された**。特に「代替案」は頻出。次の論点は「**深い②（トレードオフ）に絞るか、広い②（代替案含む）で扱うか**」と、「**その②が成果物に書かれていないか**（前に保留した laziness 交絡の確認）」。

---

## 研究の方向（有力候補）：②設計判断を「どのコード位置に残すべきか」予測（2026-05-27）

実証分析①で「②はレビューで聞かれる」が支持されたのを受けて、**進む方向として有力**と本人が判断。忘れないための記録。

**アイデア**：コードの **hunk/メソッド単位**で「ここには②設計判断（選択肢＋トレードオフ）を残しておくべき」という箇所を予測する。comment-only-commits 資産（「説明が必要と判断された箇所」ラベル）と直結。

**位置づけ＝先行研究2系統の"あいだの穴"**：
- **系統A：どこにコメント/説明を入れるべきか（コード位置レベル）** — CommtPst（Huang et al., JSS 2020, AST+LSTMでコメント位置予測）、comment necessity/usefulness 分類（コメント単位の二値分類, RF〜66%）。→ **位置は当てるが①動機か②設計根拠かを区別しない**。
- **系統B：rationale を文書化すべきか/されないか（PR・コミット単位）** — AlSafwan & Servant（VT博論 2023ほか）。commit rationale を15要素に分解し、**PRテンプレートの rationale 欄が放置されるかを統計モデルで予測**。→ **②を扱うが、コード上のどこ（hunk/メソッド）かは当てない**。
- → **「コードのどの hunk/メソッドに②を残すべきか」を予測する研究は見当たらない＝空白。** 系統Aの粒度 × 系統Bの種類（②）の交差点。

**進める前に詰める前提（批判的に）**：
1. **②は事前に予測して置くものか、聞かれたら答えるものか**。実証分析①では②の大半がレビュー中の (i)代替案提案。事前に置く価値＝「聞かれる前に置けば往復が減る」だが、時短になるかは未実証（Pascarella「回答は中央値7時間」を消せるか）。
2. **位置予測の正解ラベルをどう作るか**。「ここに②が必要だった」の ground truth が要る。**②が聞かれたレビュースレッドの diff 位置**を正解に使えば系統A×Bの隙間を一貫したデータで埋められる。

**【決定】分類対象＝「設計判断が明確に聞かれている部分」に絞る（2026-05-27 本人決定）**
- 実証分析①で保留していた「深い② vs 広い②」の分岐に決着。**広い②（(i)単なる代替案の提示を含む 43.5%）ではなく、深い②（"なぜこの方法か"・トレードオフが明示的に問われている部分）を対象**にする。
- 根拠：(i)「別のやり方の提案」は単なる suggestion で「②設計判断が問われている」とは言い切れない（実証分析①の信頼性注意でも (i) の解釈ぶれが最大のばらつき要因だった）。**「明確に聞かれている」= criteria (ii)/(iii) 寄り**で、定義が固く ground truth として信頼できる（tradeoff_explicit 10.6% の層）。
- 含意：正解ラベルは「設計判断が明確に問われたレビュースレッド」に限定 → 位置予測のターゲットも鋭くなる。母数は減るが（約1割）、ノイズが少なく主張が明確。
- TODO：実証分析①の既存ラベル（`data/sample/labels_*.jsonl`）から (ii)/(iii)・tradeoff_explicit のサブセットを抽出し直し、「明確に聞かれている」の操作的定義を確定する。

**【さらに絞り込み】抽出対象＝「聞かれて → 作者が弁明し（コード不変 or 文面回答）→ 受理された」スレッドに限定（2026-05-27 本人決定）**
- 動機：単に「なぜ？」と聞かれただけ（パターン1）では弱い。作者が黙ってコードを直したら、それは**実装者のミスの修正**であって残すべき rationale は無い。本物の②は「作者がその実装を**正当な判断として弁明し、それが受理された**」場合に限る。
- この信号で「ミス」と「本物の設計判断」を分離できる。
- **laziness 交絡も同時に解消**：受理された作者の回答＝**ground-truth の rationale**／聞かれたという事実＝**その rationale がコードに書かれていなかった証拠**（書いてあれば聞かれない）。位置予測の正解ラベル源として最良の型（実証分析①の id 27244「import が遅いので複製を選んだ」がこの型）。
- 「受理された」の観測代理：①以降そのコメント該当行が変更されていない ②スレッド resolved ③PR merged ④レビュア approve/👍。
- 弁明が「コミットメッセージ見て」等で既存成果物を指すだけなら laziness 側（情報は存在した）として除外する。

**【necessity の anchor＝レビュアが聞いたこと（2026-05-27 本人）】**
- 作者が rationale を書いた事実だけでは「そこが説明を要する箇所だった」証明にならない（過剰説明・自明の可能性）。**レビュアが聞いた＝第三者が「なぜか分からなかった」という独立した需要の証拠**。これが必要性を裏づける anchor。
- 正例は2証拠の積：**(a) レビュアが why を聞いた（需要＋コードに無かった証拠）× (b) 作者が弁明し受理された（本物の設計判断でミス修正でない）**。
- 系（重要）：**作者が自発的に書いた（聞かれていない）rationale は単体では正例にならない**。需要の証拠が無い。
- 限界（明記必須）：Pascarella の bias を継承。拾えるのは**声に出された需要だけ** → precision は高いが recall 不完全。モデルが学ぶのは「設計判断が客観的に必要な箇所」ではなく「**レビュアが聞きがちな箇所**」。学習正例としては高 precision で許容だが、主張時に断る。

**【データの壁・要対応】**
- **CodeReviewer / Comment_Generation は「1コメント＋patch」のみ**で、スレッド（作者返信）・その後のコード変更・受理状態を持たない → **この絞り込みは今のデータでは原理的に不可能**。
- 必要：レビュースレッド全体＋後続コミット差分＋解決/マージ状態が取れるデータ。**GitHub 生PRデータ（GH Archive / AIDev / API でスレッド復元）への移行が必要**。[[project-research-goal]] の「実証は GitHub/AIDev で」方針と整合。
- 次の一手：このスレッド構造＋outcome が取れるデータソースの選定（GH Archive BigQuery で review_comment＋PR timeline を join できるか確認）。

## データ収集の設計（2026-05-27 決定・着手）

**方針（本人決定）**：基盤＝**GH Archive 自前DL**（BigQuery不使用・課金なし）／スコープ＝**まず人間PRでプロトタイプ**（手法確立後に拡大）／GitHubトークン＝**未確認**（→ Stage 2 は後回し、まずアーカイブだけでオフライン完結させる）。

**必要な信号と取得元**：
| 信号 | 取得元 |
|---|---|
| レビュアが why を聞いた | review comment の `body`（粗い正規表現→後段LLM） |
| スレッド構造（誰への返信か） | `in_reply_to_id` |
| 役割（作者 or レビュア） | コメント `user.login` を payload の `pull_request.user.login` と照合 |
| コードが直されたか | review thread の `isOutdated`（GraphQL, Stage 2） |
| 受理されたか | `isResolved`＋PR `merged`（GraphQL/REST, Stage 2） |

**パイプライン**：
- **Stage 1（アーカイブ・オフライン）**：1時間ファイル(.json.gz, 最近120〜170MB/本)を1本ずつDL→`PullRequestReviewCommentEvent`だけ compact 抽出→gz削除（resumable）。`collect_gharchive.py extract <d0> <d1>`。その後 `candidates` で「why質問ルート（作者以外・非bot）×作者の返信」を窓内で突き合わせ。
- **Stage 2（要トークン・後回し）**：候補PRのみ GraphQL で `isResolved`/`isOutdated`/`merged` を取得し「弁明して受理（行不変）」を確定。
- **Stage 3**：LLM で「本物の設計why か」「返信が rationale か（既存成果物を指すだけなら laziness 除外）」を判定。

**コスト**：DL量＝1日約3.5GB／1週約25GB／1ヶ月約100GB（gzは解析後削除しディスク常駐は小）。スレッドは時間をまたぐ（返信は数時間〜数日後）ので、ペア化には数週間窓が要る。**まず1日でパーサ検証＋歩留まり（why質問/時）測定→必要窓を逆算**。

**スクリプト**：`collect_gharchive.py`（リポジトリ直下・tracked）。出力は `data/gharchive/`（gitignore済）。注意：DLは User-Agent 必須（Cloudflare がデフォルトUAを403で弾く）。

**実測歩留まり（2025-03-03 の1日・Stage 1）**：
- review comment 77,028件／日 → why質問ルート 980件（1.27%）→ **作者返信ペア候補 385件/日**（窓内ペアのみ。日跨ぎ返信は取りこぼし）。
- 品質：ランダム6件中5件が本物の②設計根拠Q&A（例 koku「なぜtransaction？」→競合状態の説明／swift「なぜこの位置に実装？」→Swift名計算の順序）。1件は作者が「理由なし、変えてよい」と譲歩＝正しく除外対象。**単一コメントのCodeReviewerより格段に低ノイズ＝ペア化が強力なフィルタ**。
- 見積もり：実質設計Q&A 約8割≒300/日。Stage 2（受理＋行不変）で仮に3〜5割残れば 100〜150 clean正例/日。→ **clean正例 約1,000件なら1週間窓（約22GB・DL30〜60分）、数千件なら2〜4週間**。律速はDL帯域のみ。
- 候補出力：`data/gharchive/candidates.jsonl`。

**留意**：①人間PRに絞るため bot/エージェント著者を除外（login の `[bot]` 等）。②`isOutdated`/`isResolved` は近似・運用まばら→使えなければ「merged＋作者返信＋行不変」に緩める。③公開リポジトリのみ（OSS狙いで問題なし）。④Pascarella bias（声に出された需要のみ＝高precision・低recall）。

**次の一手（このテーマを深掘りするなら）**：CommtPst（JSS 2020）と AlSafwan 博論を精読し、「位置×種類」を誰がどこまでやったか確定 → 空白の輪郭を固める。

## Stage 1+2 本実行の結果（2026-05-27, Windows側）

mac側は1日検証だけだったので、**1週間連続窓（2025-03-03→03-09）を本実行**。スクリプト：`collect_gharchive.py`（Stage 1）＋新規 `stage2_verify.py`（Stage 2・REST）。トークンは `.env`（gitignore済）。

**Stage 1（抽出→ペア化）**：
- review comment **453,806件/週**（約64,800/日。mac側の77,028/日よりやや低いが同オーダー）。
- why質問ルート **5,509件** → **作者返信ペア候補 2,985件**（ユニーク 2,665 PR / 2,082 repo）。連続窓で日跨ぎ取りこぼしが減り、385×7=2,695 の見積もりと整合。

**Stage 2（REST検証：merged＋ルートコメントの position）**：
| verdict | 件数 | 割合 |
|---|---|---|
| **accepted_unchanged（正例候補）** | **2,539** | **85.1%** |
| not_merged（除外） | 370 | 12.4% |
| unavailable（repo削除/private化等） | 72 | 2.4% |
| root_not_found（コメント削除等） | 4 | 0.1% |

**重要な知見（当初設計の修正）**：
- **`line_outdated`（position=null＝後で行が変わった＝ミス修正）が0件**。RESTの `position` 行不変フィルタは**追加の弁別力を持たなかった**。理由：Stage 1で既に「作者が**返信した**ペア」に限定済み＝作者が黙ってコードを直す（＝ミス修正）型は返信が無く、そもそも候補に入っていない。**行不変判定とStage 1返信フィルタは情報が重複**。実質的に効いたフィルタは not_merged 除外（12.4%）のみ。
- 当初「Stage 2で3〜5割残れば clean正例 100〜150/日」の想定に反し**85%が残存**。→ **「本物の②設計whyか／laziness除外」の選別は事実上すべて Stage 3（LLM）が担う**。
- 想定（clean正例 約1,000件）を超え **正例候補 2,539件**を1週間窓で確保。Stage 3で絞っても十分な規模が見込める。
- サンプル品質：ランダム6件中5件が本物の②（例 leanprover/KLR「なぜValueに定義？」→Termが内部にValueを持つから／PostHog「なぜdedupe？」→他ページ重複防止）。1件は作者譲歩＝Stage 3除外対象。mac側(6中5)と一致。

**Stage 2の残課題**：isResolved（GraphQL限定）は未取得。RESTのpositionが弁別しなかった以上、「受理」の強い証拠が merged のみになっている。必要なら後段でGraphQL `isResolved`/`isOutdated` を足して締めるか、Stage 3のLLM判定に委ねるかは要検討。

**Stage 3（LLM分類）結果（2026-05-27）**：
accepted_unchanged 2,539件を10シャードに分割し、サブエージェント(sonnet)10並列で分類。判定軸＝(1)design_why＝質問が本物の設計why（criteria ii「なぜこの方法か」/iii「トレードオフ」）か (2)reply_rationale＝作者返信が実際にrationaleを説明か（譲歩"I'll change it"・既存成果物参照"see commit"＝laziness は false）。正例＝両方true。スクリプト：`make_shards.py`（分割）/`merge_stage3.py`（集計・検証）。

| ラベル | 件数 | 割合 |
|---|---|---|
| **positive（正例）** | **1,094** | 43.1% |
| negative | 1,445 | 56.9% |
| （内）design_why=true | 1,269 | — |
| （内）reply_rationale=true | 1,186 | — |

- **正例の criteria 内訳**：(ii)のみ 611／(ii,iii) 473／(iii)のみ 10 → **トレードオフ明示(iii含む) 483件**。
- 全2,539件にラベル付与・重複/欠落0で検証済み。出力 `data/gharchive/stage3/positives.jsonl`（元Q&A＋criteria＋reason付き）。
- サンプル品質：vcpkg-tool「なぜmake_generic()より良い?」→「不要な\\server\share処理を避ける」／lc0「なぜハードコード?」→「新backend APIがNN topologyを露出しないため」など、本物の②設計根拠Q&Aが取れている。
- **信頼性の注意**：シャード間 positive率 31.5%〜53.1% とばらつき大（実証分析①と同じくエージェント間の基準解釈ぶれ）。43.1% は粗い推定。精密化するなら二重ラベル＋人手検証セットが必要。トレードオフ明示(iii)層の方が定義が固く信頼できる。

**到達点**：1週間窓で **clean正例 1,094件**を確保＝当初目標「約1,000件」を達成。「②設計根拠が必要だったのにコードに無かった箇所」の正解ラベル候補が揃った。

**次の一手**：
1. positives.jsonl から**位置予測の正解ラベル**を整備（どの diff hunk/行に②を残すべきか）。q_url の discussion id → REST で `original_line`/`original_start_line`/`diff_hunk` を取れば、聞かれた行＝正例位置が確定できる（Stage 2 で既にPR APIを叩く実績あり）。
2. 検証セット（人手 or 二重ラベル）で Stage 3 の precision を実測し 43.1% を較正。
3. 負例（位置予測の対照）の作り方を設計（同一PR内で聞かれなかった hunk 等）。

関連：[[project-research-goal]]、comment-only-commits 資産（[../documentation/STEERING-documentation.md](../documentation/STEERING-documentation.md)）。

---

## 保留中の論点（議論の余地・断定しない）

背景を再検討する際に改めて議論する。現時点では結論を出さず，問いとして保持する。

- **AIコードのレビューで「②設計根拠を著者に問うて得る」経路は，人間コードと同じように成立するか？**
  - 論点：AIコードの「作者」は誰か（prompt した人間か，agent 本体か）。人間の提出者は実装判断をしていない可能性。agent に後から聞くと post-hoc の説明（信頼性が疑問）。
  - 一方で，agent の生成時の reasoning trace を捕捉できれば事情は変わる（survey の(b)路線）。
  - **本人が「この"聞けない"論は変だ」と判断**（2026-05-27）。断定せず，背景検討時に再議論する。

## 次回検討候補

**まず（基礎固め）：**
- ( ) **Pascarella et al. 2018『Information Needs in Contemporary Code Review』を精読** — レビュアの7情報ニーズ（代替案の妥当性・変更の正しい理解・rationale・文脈 等）。Tao 2012・Ebert と並ぶ「情報ニーズ」の一次文献。これで土台3点セット完成。
- ( ) その後，ここまでを使って **研究の問い（research question）を文章でドラフト**する。

**研究設計・データ：**
- ( ) **AI authored vs 人間 authored PR のレビュー比較**の設計を検討（MSR'26に欠けた対照群。位置づけ判定＋工数定量化を同時に達成）。
- ( ) **AIDevデータセット**（Li/Zhang/Hassan 2025, 932k agentic PR）の中身を確認。
- ( ) **Hassan et al. 2025『Agentic Software Engineering』ロードマップ**（arXiv 2509.06216）精読＝「70%ボトルネック」の出典。

**保留・余力があれば：**
- ( ) LaToza & Mehrpour『Tool Support for Working with Design Decisions in Code』（CSUR 2024）＝②設計根拠の入口（※公開PDFにアクセスできず未取得）。
- ( ) Cihan et al. 2025『Automated code review in practice』（ICSE-SEIP）。
