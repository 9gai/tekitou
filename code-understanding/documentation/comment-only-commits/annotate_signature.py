"""
commentsテーブルにメソッドシグネチャベースの特徴量を追加する。

追加カラム:
  is_public              INTEGER  -- public修飾子があるか
  return_type_primitive  INTEGER  -- 戻り値がプリミティブ型/voidか
  method_name_word_count INTEGER  -- メソッド名の語数（CamelCase分割）
  throws_count           INTEGER  -- throws宣言の例外数

使用方法:
    python annotate_signature.py [--db dataset.db]
"""

import argparse
import re
from pathlib import Path

from tqdm import tqdm

from utils.db import get_connection

DEFAULT_DB = Path(__file__).parent / "dataset.db"
BATCH_SIZE = 1000

PRIMITIVE_TYPES = frozenset({
    "int", "long", "boolean", "float", "double", "byte", "short", "char", "void"
})
MODIFIERS = frozenset({
    "public", "protected", "private", "static", "final", "abstract",
    "synchronized", "native", "default", "transient", "volatile", "strictfp",
    "override",
})
_CAMEL_SPLIT = re.compile(r"[A-Z]?[a-z0-9]+|[A-Z]+(?=[A-Z][a-z]|[^a-zA-Z]|$)")


def _find_signature_line(method_source: str) -> str:
    """
    Javadoc・ブロックコメント・アノテーション・空行をスキップして
    最初のメソッドシグネチャ行を返す。
    """
    in_block = False
    for line in method_source.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("/*"):
            in_block = True
        if in_block:
            if "*/" in s:
                in_block = False
            continue
        if s.startswith("//") or s.startswith("@"):
            continue
        return s
    return ""


def extract_signature_features(
    method_source: str,
) -> tuple[int | None, int | None, int | None, int | None]:
    """
    シグネチャからメソッド特徴量を抽出する。
    パース失敗時はすべて None を返す。
    """
    if not method_source or not method_source.strip():
        return None, None, None, None

    sig_line = _find_signature_line(method_source)
    if not sig_line or "(" not in sig_line:
        return None, None, None, None

    # is_public
    is_public = 1 if re.search(r"\bpublic\b", sig_line) else 0

    # シグネチャの '(' より前のトークン列を取得
    before_paren = sig_line[: sig_line.index("(")]
    tokens = re.split(r"\s+", before_paren.strip())

    # 修飾子・アノテーション・ジェネリクスを除去
    meaningful = []
    for t in tokens:
        t_clean = re.sub(r"<[^>]*>", "", t).strip()  # remove <T>
        t_clean = re.sub(r"\[\]", "", t_clean)        # remove []
        if t_clean and t_clean not in MODIFIERS and not t_clean.startswith("@"):
            meaningful.append(t_clean)

    if len(meaningful) < 2:
        # コンストラクタまたはパース失敗
        return is_public, None, None, None

    return_type_raw = meaningful[0]
    method_name = meaningful[-1]

    # return_type_primitive
    return_type_primitive = 1 if return_type_raw in PRIMITIVE_TYPES else 0

    # method_name_word_count
    words = _CAMEL_SPLIT.findall(method_name)
    word_count = max(len(words), 1)

    # throws_count: シグネチャ付近の先頭5行を結合して検索
    head = " ".join(method_source.splitlines()[:5])
    throws_match = re.search(r"\bthrows\b\s+([\w\s,.<>]+?)(?:\{|$)", head)
    throws_count = 0
    if throws_match:
        throws_text = throws_match.group(1)
        throws_count = len([t for t in throws_text.split(",") if t.strip()])

    return is_public, return_type_primitive, word_count, throws_count


def _add_columns(conn) -> None:
    for col, definition in [
        ("is_public",              "INTEGER"),
        ("return_type_primitive",  "INTEGER"),
        ("method_name_word_count", "INTEGER"),
        ("throws_count",           "INTEGER"),
    ]:
        try:
            conn.execute(f"ALTER TABLE comments ADD COLUMN {col} {definition}")
            conn.commit()
            print(f"  カラム追加: {col}")
        except Exception:
            pass  # already exists


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    conn = get_connection(args.db)
    _add_columns(conn)

    rows = conn.execute(
        "SELECT id, target_method FROM comments "
        "WHERE target_method IS NOT NULL AND target_method != '' "
        "AND is_public IS NULL"
    ).fetchall()
    conn.close()

    print(f"{len(rows)} 件のシグネチャ特徴量を計算します ...")

    batch: list[tuple] = []
    conn = get_connection(args.db)

    try:
        for row in tqdm(rows, desc="シグネチャ解析中"):
            is_pub, rt_prim, wc, tc = extract_signature_features(row["target_method"])
            batch.append((is_pub, rt_prim, wc, tc, row["id"]))

            if len(batch) >= BATCH_SIZE:
                conn.executemany(
                    "UPDATE comments SET "
                    "is_public=?, return_type_primitive=?, "
                    "method_name_word_count=?, throws_count=? "
                    "WHERE id=?",
                    batch,
                )
                conn.commit()
                batch.clear()

        if batch:
            conn.executemany(
                "UPDATE comments SET "
                "is_public=?, return_type_primitive=?, "
                "method_name_word_count=?, throws_count=? "
                "WHERE id=?",
                batch,
            )
            conn.commit()
    finally:
        conn.close()

    print("完了")

    # 結果確認
    conn = get_connection(args.db)
    import sys
    for col in ["is_public", "return_type_primitive", "method_name_word_count", "throws_count"]:
        row = conn.execute(
            f"SELECT AVG({col}), MIN({col}), MAX({col}), "
            f"COUNT(*) FROM comments WHERE {col} IS NOT NULL"
        ).fetchone()
        sys.stdout.buffer.write(
            f"{col}: avg={row[0]:.3f}, min={row[1]}, max={row[2]}, n={row[3]}\n".encode()
        )
    conn.close()


if __name__ == "__main__":
    main()
