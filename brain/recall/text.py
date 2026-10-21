"""Vietnamese-aware normalisation for the Recall index (spec v4 §4).

FTS5 `remove_diacritics` does not map đ→d (checked 2026-10-21), so text is normalised before it is indexed
and queries go through the same function.
"""
from __future__ import annotations

import re
import unicodedata

STOP = set("""va la cua cho khi thi the duoc mot cac nhung de trong voi khong co nay do da se dang can phai
neu vi tu den theo ra vao len hay hoac rat nhu nao gi ai sao bang hon nhat cung con moi tung ban toi minh
the and or for with from that this into when then than not are was were has have had but use using new old""".split())
TOKEN = re.compile(r"[a-z0-9_]{2,}")


def norm(s: str) -> str:
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def terms(s: str) -> list[str]:
    seen, out = set(), []
    for t in TOKEN.findall(norm(s)):
        if t not in STOP and not t.isdigit() and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def fts_query(s: str, max_terms: int = 12) -> str:
    """OR of quoted terms; empty string means 'nothing to search'."""
    ts = terms(s)[:max_terms]
    return " OR ".join(f'"{t}"' for t in ts)


PATHLIKE = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]{1,5})(?![\w/])")


def paths_in(s: str) -> list[str]:
    """Repo-relative file paths mentioned in a text (`src/x.py`, `config/plugins.toml`)."""
    return sorted({m.group(1).strip("`'\".,") for m in PATHLIKE.finditer(s or "")})
