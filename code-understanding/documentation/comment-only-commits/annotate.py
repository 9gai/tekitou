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


def compute_complexity(method_source: str) -> tuple[float, int, int]:
    """
    Lizardを使って循環複雑度・LOC・引数の数を計算する。
    method_sourceをtmpファイルに書き出して解析する。
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


def compute_identifier_metrics(method_source: str) -> tuple[float, float]:
    """
    メソッドソースから識別子名の平均長と略称率を計算する。
    Javaキーワードは除外する。
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

    with get_connection(args.db) as conn:
        rows = conn.execute(
            "SELECT id, target_method FROM comments WHERE cyclomatic_complexity IS NULL"
        ).fetchall()

    print(f"{len(rows)} 件の属性を計算します ...")

    for row in tqdm(rows, desc="属性付与中"):
        comment_id = row["id"]
        method_source = row["target_method"] or ""

        if not method_source.strip():
            continue

        cc, loc, param_count = compute_complexity(method_source)
        avg_len, abbrev_ratio = compute_identifier_metrics(method_source)

        with get_connection(args.db) as conn:
            conn.execute(
                """
                UPDATE comments SET
                    cyclomatic_complexity = ?,
                    loc                   = ?,
                    parameter_count       = ?,
                    avg_identifier_length = ?,
                    abbrev_ratio          = ?
                WHERE id = ?
                """,
                (cc, loc, param_count, avg_len, abbrev_ratio, comment_id),
            )
            conn.commit()

    print("完了")


if __name__ == "__main__":
    main()
