"""`brain clean …` and `brain promote` (spec §5).

backup / verify-backup / diff-facts / retire are ported from v2 `clean-memory/scripts/clean_memory.py`
(0.4.0): nothing is deleted, every move needs a same-day backup, and a large CONTEXT rewrite is checked
with diff-facts first (ACE: whole rewrites collapsed context 18,282 → 122 tokens; v2 found 131-136
facts that would have vanished). v3 adds D-NNN ids and the hub `_archive/` location.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from brain import paths
from brain.project import Project, all_projects

MANIFEST, META = "MANIFEST.sha256", "meta.json"
FACT_PATTERNS = {
    "id": r"\b(?:DP|S|B|ADR|D|M|OPS)-\d+\b",
    "commit": r"(?<![\w/.-])[0-9a-f]{7,40}(?![\w/-])",
    "số": r"(?<![\w.,-])\d{1,3}(?:[.,]\d{3})+(?![\d])|(?<![\w.,-])\d+[.,]\d+%?(?![\d])|(?<![\w.,-])\d{3,}(?![\w.,-])|(?<![\w.,-])\d+%",
    "code": r"`([^`\n]{2,80})`",
}


def _sha(f: Path) -> str:
    return hashlib.sha256(f.read_bytes()).hexdigest()


def archive_dir(p: Project) -> Path:
    return p.root.parent.parent / "_archive"


def retired_dir(p: Project) -> Path:
    return archive_dir(p) / f"{p.name}-retired"


# ---------------------------------------------------------------- diff-facts
def extract_facts(text: str) -> dict[str, str]:
    """→ {fact token: kind}. A commit must mix digits and a-f (rules out 1234567 and plain words)."""
    facts: dict[str, str] = {}
    for kind, pat in FACT_PATTERNS.items():
        for m in re.finditer(pat, text):
            tok = (m.group(1) if m.groups() else m.group(0)).strip()
            if kind == "commit" and not (re.search(r"\d", tok) and re.search(r"[a-f]", tok)):
                continue
            if tok:
                facts.setdefault(tok, kind)
    return facts


def diff_facts(old: Path, new: Path, search: list[Path]) -> dict:
    old_f, new_text = extract_facts(old.read_text(encoding="utf-8")), new.read_text(encoding="utf-8")
    lost = {t: k for t, k in old_f.items() if t not in new_text}
    corpus = []
    skip = {old.resolve(), new.resolve()}
    for base in search:
        files = [base] if base.is_file() else (sorted(f for f in base.rglob("*") if f.is_file()) if base.is_dir() else [])
        for f in files:
            if f.resolve() in skip or f.suffix not in (".md", ".tsv", ".txt", ".toml", ".json", ""):
                continue
            try:
                corpus.append((f, f.read_text(encoding="utf-8", errors="ignore")))
            except OSError:
                continue
    kept, gone = {}, {}
    for tok, kind in lost.items():
        hit = next((f for f, text in corpus if tok in text), None)
        if hit is not None:
            kept[tok] = paths.fwd(hit)
        else:
            gone[tok] = kind
    return {"facts_old": len(old_f), "lost": len(lost), "kept_elsewhere": kept, "gone": gone}


# ---------------------------------------------------------------- backup / verify
def backup(p: Project, note: str = "") -> Path:
    dest = archive_dir(p) / f"{p.name}-clean-{datetime.now():%Y%m%d-%H%M%S}"
    if dest.exists():
        raise SystemExit(f"❌ {paths.fwd(dest)} đã tồn tại")
    shutil.copytree(p.root, dest / "project", symlinks=True, ignore=shutil.ignore_patterns(".state"))
    g = p.root.parent.parent / "_global"
    if g.is_dir():
        shutil.copytree(g, dest / "_global", symlinks=True)
    (dest / META).write_text(json.dumps({"project": p.name, "source": paths.fwd(p.root), "note": note,
                                         "created": datetime.now().isoformat(timespec="seconds")},
                                        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = sorted(f for f in dest.rglob("*") if f.is_file() and f.name != MANIFEST)
    (dest / MANIFEST).write_text("".join(f"{_sha(f)}  {f.relative_to(dest).as_posix()}\n" for f in files), encoding="utf-8")
    return dest


def verify_backup(p: Project, bdir: Path) -> dict:
    man = bdir / MANIFEST
    if not man.is_file() or not (bdir / META).is_file():
        raise SystemExit(f"❌ {paths.fwd(bdir)} không phải bản backup của brain (thiếu {MANIFEST}/{META})")
    corrupt, status = [], {"same": [], "changed": [], "retired": [], "missing": []}
    retired = retired_dir(p)
    retired_hashes = {_sha(f) for f in retired.rglob("*") if f.is_file()} if retired.is_dir() else set()
    for line in man.read_text(encoding="utf-8").splitlines():
        digest, rel = line.split("  ", 1)
        f = bdir / rel
        if not f.is_file() or _sha(f) != digest:
            corrupt.append(rel)
        if not rel.startswith("project/"):
            continue
        inner = rel[len("project/"):]
        cur = p.root / inner
        if cur.is_file():
            status["same" if _sha(cur) == digest else "changed"].append(inner)
        elif digest in retired_hashes or (retired / inner).is_file():
            status["retired"].append(inner)
        else:
            status["missing"].append(inner)
    return {"corrupt": corrupt, **status}


def _has_backup_today(p: Project) -> bool:
    prefix = f"{p.name}-clean-{datetime.now():%Y%m%d}-"
    return any(d.name.startswith(prefix) and (d / MANIFEST).is_file() for d in archive_dir(p).glob(f"{prefix}*"))


# ---------------------------------------------------------------- retire
def retire(p: Project, files: list[str], reason: str, dry: bool = False) -> list[str]:
    plan = []
    root = p.root.resolve()
    for raw in files:
        src = Path(raw).expanduser()
        src = (src if src.is_absolute() else p.root / src).resolve()
        if root not in src.parents:
            raise SystemExit(f"❌ {raw}: không nằm trong {paths.fwd(p.root)}")
        if not src.is_file():
            raise SystemExit(f"❌ {raw}: không phải file")
        rel = src.relative_to(root)
        dst = retired_dir(p) / rel
        if dst.exists():
            dst = dst.with_name(f"{dst.stem}-{datetime.now():%Y%m%d-%H%M%S}{dst.suffix}")
        plan.append((src, rel, dst))
    lines = [f"{'(dry-run) ' if dry else ''}retire {r.as_posix()} → {paths.fwd(d)}" for _, r, d in plan]
    if dry:
        return lines
    if not _has_backup_today(p):
        raise SystemExit(f"❌ chưa có backup hôm nay của {p.name} — chạy `brain clean backup` trước")
    idx = retired_dir(p) / "INDEX.md"
    if not idx.exists():
        idx.parent.mkdir(parents=True, exist_ok=True)
        idx.write_text(f"# Retired — {p.name}\n\n> Chuyển ra bởi `brain clean retire`. Không xoá.\n\n"
                       "| Ngày | File gốc | sha256 (12) | Lý do |\n|---|---|---|---|\n", encoding="utf-8")
    with idx.open("a", encoding="utf-8") as fh:
        for src, rel, dst in plan:
            digest = _sha(src)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            fh.write(f"| {datetime.now():%Y-%m-%d} | `{rel.as_posix()}` | `{digest[:12]}` | {reason} |\n")
    return lines


# ---------------------------------------------------------------- promote
def _norm_title(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def promote(p: Project, min_days: int = 2) -> dict:
    """Ladder step 2→3 (spec §2, v2.1 rule 5): traps seen on ≥ min_days distinct days with nothing enforcing them,
    plus traps whose title also appears in another v3 project (candidate for _global/traps.md)."""
    ready = [t for t in p.traps() if len(set(t.seen)) >= min_days and t.enforce in ("", "none")]
    others: dict[str, list[str]] = {}
    for q in all_projects(p.root.parent.parent):
        if q.name == p.name:
            continue
        for t in q.traps():
            others.setdefault(_norm_title(t.title), []).append(f"{q.name}:{t.id}")
    shared = [(t, others[_norm_title(t.title)]) for t in p.traps() if _norm_title(t.title) in others]
    return {"ready": ready, "shared": shared}
