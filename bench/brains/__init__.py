from bench.brains.base import Brain, Env
from bench.brains.none import NoBrain
from bench.brains.v1 import V1
from bench.brains.v2 import V2
from bench.brains.v3 import V3
from bench.brains.v4 import V4

BRAINS: dict[str, type[Brain]] = {b.name: b for b in (NoBrain, V1, V2, V3, V4)}


def get_brain(name: str) -> Brain:
    try:
        return BRAINS[name]()
    except KeyError:
        raise SystemExit(f"Không có brain '{name}'. Có: {', '.join(BRAINS)}") from None


__all__ = ["BRAINS", "Brain", "Env", "get_brain"]
