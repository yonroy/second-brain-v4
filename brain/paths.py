"""Hub / project resolution and Windows ↔ WSL path handling (ADR-001)."""
from __future__ import annotations

import os
import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent
_DRIVE = re.compile(r"^([A-Za-z]):[\\/]")
_MNT = re.compile(r"^/mnt/([a-z])/")


def fwd(p) -> str:
    """Stored form of a path: forward slashes, Windows drive kept (D:/x/y)."""
    s = str(p).replace("\\", "/")
    m = _MNT.match(s)
    return f"{m.group(1).upper()}:/{s[m.end():]}" if m else s


def local(p) -> Path:
    """Stored path → a path this interpreter can open (D:/x → /mnt/d/x under WSL/Linux)."""
    s = str(p).replace("\\", "/")
    if os.name != "nt":
        m = _DRIVE.match(s)
        if m:
            return Path(f"/mnt/{m.group(1).lower()}/{s[m.end():]}")
    return Path(s)


def same_path(a, b) -> bool:
    na, nb = fwd(a).rstrip("/"), fwd(b).rstrip("/")
    return na.lower() == nb.lower() if (_DRIVE.match(na) or os.name == "nt") else na == nb


def hub() -> Path:
    env = os.environ.get("SECOND_BRAIN_V3_ROOT", "").strip()
    h = local(env) if env else PACKAGE.parent
    try:
        return h.resolve()  # one spelling everywhere (expands Windows 8.3 short names)
    except OSError:
        return h


def projects_dir(h: Path | None = None) -> Path:
    return (h or hub()) / "_projects"


def brain_cmd() -> str:
    """How CLAUDE.md / hooks invoke this CLI."""
    return f'python "{fwd(PACKAGE)}/bin/brain.py"'
