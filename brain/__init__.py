"""Second Brain v4 CLI. Generation-specific names live here so v3 and v4 can coexist on one machine (ADR-009)."""
from pathlib import Path

VERSION = (Path(__file__).resolve().parent.parent / "VERSION").read_text(encoding="utf-8").strip()
GEN = 4
HUB_ENV = "SECOND_BRAIN_V4_ROOT"
BLOCK = "SECOND-BRAIN-V4"
LEGACY_BLOCKS = ("SECOND-BRAIN-V3", "SECOND-BRAIN-V2")
