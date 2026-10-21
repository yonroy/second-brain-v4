import importlib
import json
import pathlib
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load(ref):
    mod, fn = ref.split(":")
    return getattr(importlib.import_module(mod), fn)


def dispatch(event, payload):
    table = tomllib.loads((ROOT / "config" / "plugins.toml").read_text(encoding="utf-8"))["events"]
    return _load(table[event])(payload)


def run_schedules():
    from src import handlers
    jobs = json.loads((ROOT / "data" / "schedules.json").read_text(encoding="utf-8"))
    return [getattr(handlers, j["handler"])(j["payload"]) for j in jobs]
