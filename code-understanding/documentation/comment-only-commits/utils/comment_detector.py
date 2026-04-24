"""
Javaのコメント行を判定するユーティリティ。
文字列リテラル内の // を誤検出しないよう，行単位の簡易ステートマシンで処理する。
"""

import re

_COMMENT_PREFIX = re.compile(r"^\s*(//|/\*\*|/\*|\*)")

CLARIFY_KEYWORDS = re.compile(
    r"\b(clarif|explain|confus|tricky|complex|document|why|workaround|hack|note)\w*\b",
    re.IGNORECASE,
)

# GitHubの自動クローズキーワード（refs/bare #NNN は含まない）
# 例: "fixes #123", "closes org/repo#456", "resolves #78"
_AUTOCLOSE_REF = re.compile(
    r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+"
    r"(?:[\w.\-]+/[\w.\-]+)?"  # optional org/repo prefix
    r"#(\d+)",
    re.IGNORECASE,
)

# auto-close issue番号抽出用
_AUTOCLOSE_EXTRACT = re.compile(
    r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+"
    r"([\w.\-]+/[\w.\-]+)?#(\d+)",
    re.IGNORECASE,
)

# GitHub auto-close keywords + bare/refs patterns
# 例: "fixes #123", "closes org/repo#456", "refs #78", "#99"
_ISSUE_REF = re.compile(
    r"(?:"
    r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|ref(?:erence[sd]?)?)\s+"
    r"(?:[\w.\-]+/[\w.\-]+)?"  # optional org/repo prefix
    r"|"
    r"(?:[\w.\-]+/[\w.\-]+)"   # org/repo#NNN standalone
    r")"
    r"#\d+"
    r"|"
    r"(?<!\w)#\d+",            # bare #NNN (not preceded by word char)
    re.IGNORECASE,
)

# issue番号抽出用（org/repoプレフィックスとissue番号をキャプチャ）
_ISSUE_EXTRACT = re.compile(
    r"(?:(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|ref(?:erence[sd]?)?)\s+)?"
    r"([\w.\-]+/[\w.\-]+)?#(\d+)",
    re.IGNORECASE,
)

# issueがコードの難解さに関するものかを判定するキーワード
# 肯定シグナル：理解困難・説明要求・ドキュメント不足
COMPLEXITY_KEYWORDS = re.compile(
    r"\b("
    r"confus|unclear|hard\s+to\s+(read|understand|follow)|"
    r"difficult\s+to\s+(read|understand|follow)|"
    r"not\s+(clear|obvious|documented|understandable)|"
    r"what\s+does|why\s+(is|does|are|was|were|do)|"
    r"explain|clarif|document|undocumented|"
    r"complex|tricky|mislead|ambiguous|opaque|"
    r"poorly\s+(documented|written|named|commented)|"
    r"missing\s+(comment|doc|documentation|javadoc)|"
    r"no\s+(comment|doc|documentation|javadoc)"
    r")\w*\b",
    re.IGNORECASE,
)

# 強い否定シグナル：バグ・クラッシュ・パフォーマンス・機能追加は除外
_NEGATIVE_SIGNALS = re.compile(
    r"\b("
    r"NPE|NullPointer|exception|crash|error|fail|bug|broken|"
    r"performance|slow|memory|leak|timeout|deadlock|"
    r"implement|add\s+(support|feature)|new\s+feature|enhancement|request"
    r")\w*\b",
    re.IGNORECASE,
)

TEST_FILE_PATTERN = re.compile(r"(Test|Tests|TestCase)\.java$")
GENERATED_PATTERN = re.compile(r"@Generated")


def is_comment_line(line: str) -> bool:
    """空白行またはJavaコメント行であればTrueを返す。"""
    stripped = line.strip()
    if not stripped:
        return True
    return bool(_COMMENT_PREFIX.match(line))


def classify_comment(lines: list[str]) -> str:
    """追加されたコメント行のリストからコメント種別を返す。"""
    joined = "\n".join(l.strip() for l in lines)
    if joined.startswith("/**"):
        return "javadoc"
    if joined.startswith("/*"):
        return "block"
    return "inline"


def has_clarify_keyword(message: str) -> bool:
    """コミットメッセージが「明確化」を示すキーワードを含むか。"""
    return bool(CLARIFY_KEYWORDS.search(message or ""))


def has_autoclose_keyword(message: str) -> bool:
    """fixes/closes/resolves #NNN 形式の自動クローズキーワードを含むか（refs/bare #NNN は除外）。"""
    return bool(_AUTOCLOSE_REF.search(message or ""))


def extract_autoclose_issues(message: str) -> list[tuple[str | None, int]]:
    """
    自動クローズキーワード付きのissue番号を抽出する。
    Returns: list of (repo_override_or_None, issue_number)
    """
    results = []
    for m in _AUTOCLOSE_EXTRACT.finditer(message or ""):
        repo_override = m.group(1) or None
        issue_number = int(m.group(2))
        results.append((repo_override, issue_number))
    return results


def has_issue_reference(message: str) -> bool:
    """コミットメッセージにGitHub issueへの参照（fixes #123 等）が含まれるか。"""
    return bool(_ISSUE_REF.search(message or ""))


def extract_issue_numbers(message: str) -> list[tuple[str | None, int]]:
    """
    コミットメッセージからissue参照を抽出する。
    Returns: list of (repo_override_or_None, issue_number)
      repo_override が None の場合は同一リポジトリのissue
    """
    results = []
    for m in _ISSUE_EXTRACT.finditer(message or ""):
        repo_override = m.group(1) or None
        issue_number = int(m.group(2))
        results.append((repo_override, issue_number))
    return results


def is_complexity_related(text: str) -> bool:
    """
    issue のタイトル+本文がコードの難解さ・理解困難に関するものかを判定する。
    肯定シグナルありかつ強い否定シグナルなし，の場合に True を返す。
    """
    text = text or ""
    if not COMPLEXITY_KEYWORDS.search(text):
        return False
    if _NEGATIVE_SIGNALS.search(text):
        return False
    return True


def is_test_file(path: str) -> bool:
    return bool(TEST_FILE_PATTERN.search(path))


def has_generated_annotation(source: str) -> bool:
    return bool(GENERATED_PATTERN.search(source or ""))
