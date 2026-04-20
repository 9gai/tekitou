"""
commentsテーブルの未入力属性（複雑度・識別子名品質）を計算して埋める。

使用方法:
    python annotate.py [--db dataset.db]
"""

import argparse
import re
import tempfile
from pathlib import Path

import lizard
from tqdm import tqdm

from utils.db import get_connection

DEFAULT_DB = Path(__file__).parent / "dataset.db"
BATCH_SIZE = 500

IDENTIFIER_PATTERN = re.compile(r"\b[a-zA-Z_]\w*\b")
JAVA_KEYWORDS = frozenset({
    "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char",
    "class", "const", "continue", "default", "do", "double", "else", "enum",
    "extends", "final", "finally", "float", "for", "goto", "if", "implements",
    "import", "instanceof", "int", "interface", "long", "native", "new",
    "package", "private", "protected", "public", "return", "short", "static",
    "strictfp", "super", "switch", "synchronized", "this", "throw", "throws",
    "transient", "try", "void", "volatile", "while", "true", "false", "null",
})

# cognitive complexity で+1されるキーワード（ネスト深度で重みが変わる）
_NESTING_KEYWORDS = re.compile(
    r"\b(if|else\s+if|else|for|while|do|switch|catch)\b|(\?\s*[^:]+\s*:)"
)
# 論理演算子（フラット+1）
_LOGICAL_OPS = re.compile(r"&&|\|\|")
# ネスト深度を増やす構造
_OPEN_BRACE = re.compile(r"\{")
_CLOSE_BRACE = re.compile(r"\}")


def compute_complexity(method_source: str) -> tuple[float, int, int]:
    """
    Lizardを使って循環複雑度・LOC・引数の数を計算する。
    """
    with tempfile.NamedTemporaryFile(suffix=".java", mode="w", encoding="utf-8", delete=False) as f:
        f.write(f"class _Wrapper {{\n{method_source}\n}}")
        tmp_path = f.name

    try:
        result = lizard.analyze_file(tmp_path)
        if result and result.function_list:
            fn = result.function_list[0]
            return fn.cyclomatic_complexity, fn.length, fn.parameter_count
    except Exception:
        pass
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return 0.0, 0, 0


def compute_cognitive_complexity(method_source: str) -> float:
    """
    SonarSource定義に基づく簡易Cognitive Complexity計算。
    - 制御構造（if/else/for/while/do/switch/catch）に +1（+ ネスト深度分）
    - 論理演算子（&&/||）に +1（フラット）
    ネスト深度はブレースの数で追跡する近似。
    """
    depth = 0
    score = 0
    for line in method_source.splitlines():
        # ブレースでネスト深度を更新
        depth += line.count("{") - line.count("}")
        depth = max(0, depth)

        # 制御構造
        for _ in _NESTING_KEYWORDS.finditer(line):
            score += 1 + max(0, depth - 1)  # ネストボーナス

        # 論理演算子
        score += len(_LOGICAL_OPS.findall(line))

    return float(score)


def compute_identifier_metrics(method_source: str) -> tuple[float, float]:
    """
    識別子名の平均長と略称率を計算する。Javaキーワードは除外。
    """
    tokens = IDENTIFIER_PATTERN.findall(method_source)
    identifiers = [t for t in tokens if t not in JAVA_KEYWORDS]
    if not identifiers:
        return 0.0, 0.0

    avg_len = sum(len(i) for i in identifiers) / len(identifiers)
    abbrev_count = sum(1 for i in identifiers if len(i) <= 3)
    abbrev_ratio = abbrev_count / len(identifiers)
    return avg_len, abbrev_ratio


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    conn = get_connection(args.db)
    rows = conn.execute(
        "SELECT id, target_method FROM comments "
        "WHERE cyclomatic_complexity IS NULL "
        "AND target_method IS NOT NULL AND target_method != ''"
    ).fetchall()
    conn.close()

    print(f"{len(rows)} 件の属性を計算します ...")

    batch: list[tuple] = []
    conn = get_connection(args.db)

    try:
        for row in tqdm(rows, desc="属性付与中"):
            comment_id = row["id"]
            method_source = row["target_method"]

            cc, loc, param_count = compute_complexity(method_source)
            cog = compute_cognitive_complexity(method_source)
            avg_len, abbrev_ratio = compute_identifier_metrics(method_source)

            batch.append((cc, cog, loc, param_count, avg_len, abbrev_ratio, comment_id))

            if len(batch) >= BATCH_SIZE:
                conn.executemany(
                    """
                    UPDATE comments SET
                        cyclomatic_complexity = ?,
                        cognitive_complexity  = ?,
                        loc                   = ?,
                        parameter_count       = ?,
                        avg_identifier_length = ?,
                        abbrev_ratio          = ?
                    WHERE id = ?
                    """,
                    batch,
                )
                conn.commit()
                batch.clear()

        # 残りをflush
        if batch:
            conn.executemany(
                """
                UPDATE comments SET
                    cyclomatic_complexity = ?,
                    cognitive_complexity  = ?,
                    loc                   = ?,
                    parameter_count       = ?,
                    avg_identifier_length = ?,
                    abbrev_ratio          = ?
                WHERE id = ?
                """,
                batch,
            )
            conn.commit()
    finally:
        conn.close()

    print("完了")


if __name__ == "__main__":
    main()
