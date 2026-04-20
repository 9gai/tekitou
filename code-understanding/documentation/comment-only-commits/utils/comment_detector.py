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


def has_issue_reference(message: str) -> bool:
    """コミットメッセージにGitHub issueへの参照（fixes #123 等）が含まれるか。"""
    return bool(_ISSUE_REF.search(message or ""))


def is_test_file(path: str) -> bool:
    return bool(TEST_FILE_PATTERN.search(path))


def has_generated_annotation(source: str) -> bool:
    return bool(GENERATED_PATTERN.search(source or ""))
