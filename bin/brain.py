"""Launcher usable from any cwd: python D:/SecondBrainV3/Brain/bin/brain.py <cmd>."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brain.cli import main  # noqa: E402

raise SystemExit(main())
