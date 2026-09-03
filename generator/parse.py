"""
Data extraction for the Terra Mirabilis documentation generator.

Reads the mod's own SQL as the single source of truth, with no third-party
dependencies (standard library only):

  * INSERT INTO <Table> (cols) VALUES (...), (...);   -> table rows
  * INSERT ... INTO LocalizedText (Language, Tag, Text) VALUES ...
        -> LOC_* -> English (en_US) string table

The SQL is not executed. A small tokenizer extracts the INSERT rows while
respecting `-- ...` / `/* ... */` comments and BOTH string-literal styles Civ's
SQL allows: single quotes (with `''` escaping) and double quotes (with `""`
escaping). Terra Mirabilis' localisation file quotes most text with `"..."` but
switches to `'...'` for lines that contain an apostrophe, so a scanner that
understands only one style would mis-tokenise the file.
"""

from __future__ import annotations

import os
import re
import glob
from collections import defaultdict


_QUOTES = ("'", '"')


def strip_sql_comments(sql: str) -> str:
    """Remove `-- ...` line comments and `/* ... */` blocks, leaving string
    literals (either quote style) untouched so a `--` inside a string or an
    apostrophe inside a comment cannot confuse us."""
    out = []
    i, n = 0, len(sql)
    quote = None  # current opening quote char, or None
    while i < n:
        c = sql[i]
        if quote is not None:
            out.append(c)
            if c == quote:
                if i + 1 < n and sql[i + 1] == quote:   # doubled -> escaped
                    out.append(quote)
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if c in _QUOTES:
            quote = c
            out.append(c)
            i += 1
            continue
        if c == "-" and i + 1 < n and sql[i + 1] == "-":
            j = sql.find("\n", i)
            if j == -1:
                break
            i = j
            continue
        if c == "/" and i + 1 < n and sql[i + 1] == "*":
            j = sql.find("*/", i + 2)
            i = (j + 2) if j != -1 else n
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _split_top_level(s: str, sep: str = ",") -> list[str]:
    """Split on `sep` at paren-depth 0, ignoring separators inside strings."""
    parts, buf = [], []
    depth = 0
    quote = None
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if quote is not None:
            buf.append(c)
            if c == quote:
                if i + 1 < n and s[i + 1] == quote:
                    buf.append(quote)
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if c in _QUOTES:
            quote = c
            buf.append(c)
        elif c == "(":
            depth += 1
            buf.append(c)
        elif c == ")":
            depth -= 1
            buf.append(c)
        elif c == sep and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(c)
        i += 1
    if buf:
        parts.append("".join(buf))
    return parts


def _parse_value(tok: str):
    tok = tok.strip()
    if tok == "" or tok.upper() == "NULL":
        return None
    if len(tok) >= 2 and tok[0] in _QUOTES and tok[-1] == tok[0]:
        q = tok[0]
        return tok[1:-1].replace(q + q, q)
    return tok  # bareword / number / true / false


def _split_tuples(values_blob: str) -> list[str]:
    """Given the text after VALUES, return each top-level `( ... )` group."""
    tuples = []
    depth = 0
    quote = None
    start = None
    i, n = 0, len(values_blob)
    while i < n:
        c = values_blob[i]
        if quote is not None:
            if c == quote:
                if i + 1 < n and values_blob[i + 1] == quote:
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if c in _QUOTES:
            quote = c
        elif c == "(":
            if depth == 0:
                start = i + 1
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0 and start is not None:
                tuples.append(values_blob[start:i])
                start = None
        i += 1
    return tuples


def _split_statements(sql: str) -> list[str]:
    """Split cleaned SQL on `;` at paren-depth 0 and outside any string. A single
    `INSERT ... VALUES (..),(..);` can span the whole file and its text may itself
    contain `;` inside a quoted string, so a naive split on `;` would truncate it."""
    stmts, buf = [], []
    depth = 0
    quote = None
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if quote is not None:
            buf.append(c)
            if c == quote:
                if i + 1 < n and sql[i + 1] == quote:
                    buf.append(quote)
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if c in _QUOTES:
            quote = c
            buf.append(c)
        elif c == "(":
            depth += 1
            buf.append(c)
        elif c == ")":
            depth -= 1
            buf.append(c)
        elif c == ";" and depth == 0:
            stmts.append("".join(buf))
            buf = []
        else:
            buf.append(c)
        i += 1
    if buf:
        stmts.append("".join(buf))
    return stmts


# Head of an INSERT statement: INSERT [OR REPLACE|IGNORE] INTO <table> (<cols>) VALUES
_INSERT_HEAD_RE = re.compile(
    r"INSERT\s+(?:OR\s+(?:REPLACE|IGNORE)\s+)?INTO\s+"
    r"([A-Za-z_][A-Za-z0-9_]*)\s*\((.*?)\)\s*VALUES\s*",
    re.IGNORECASE | re.DOTALL,
)


def _read_text(path: str) -> str:
    with open(path, "rb") as fh:
        blob = fh.read()
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return blob.decode(enc)
        except UnicodeDecodeError:
            continue
    return blob.decode("utf-8", errors="replace")


def parse_sql_file(path: str, tables: dict[str, list[dict]]):
    clean = strip_sql_comments(_read_text(path))
    for stmt in _split_statements(clean):
        m = _INSERT_HEAD_RE.match(stmt.lstrip())
        if not m:
            continue
        table = m.group(1)
        cols = [c.strip() for c in _split_top_level(m.group(2))]
        rest = stmt.lstrip()[m.end():]
        for tup in _split_tuples(rest):
            vals = [_parse_value(v) for v in _split_top_level(tup)]
            if len(vals) != len(cols):
                continue  # tolerate the odd malformed row rather than crash
            tables[table].append(dict(zip(cols, vals)))


def load_sql_tree(root: str) -> dict[str, list[dict]]:
    """Parse every *.sql under `root` into {table_name: [row, ...]}."""
    tables: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(glob.glob(os.path.join(root, "**", "*.sql"), recursive=True)):
        try:
            parse_sql_file(path, tables)
        except Exception as exc:  # noqa: BLE001 - keep going, report at end
            print(f"  ! failed to parse {os.path.relpath(path, root)}: {exc}")
    return tables


def load_text(tables: dict[str, list[dict]], language: str = "en_US") -> dict[str, str]:
    """Build the LOC_* -> text map from parsed LocalizedText rows."""
    loc: dict[str, str] = {}
    for row in tables.get("LocalizedText", []):
        if row.get("Language") != language:
            continue
        tag, text = row.get("Tag"), row.get("Text")
        if tag and text is not None:
            loc[tag] = text
    return loc


if __name__ == "__main__":
    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    tables = load_sql_tree(os.path.join(ROOT, "Core"))
    loc = load_text(tables)
    print(f"tables parsed: {len(tables)}")
    for t in sorted(tables):
        print(f"  {t:28} {len(tables[t])} rows")
    print(f"loc keys (en_US): {len(loc)}")
