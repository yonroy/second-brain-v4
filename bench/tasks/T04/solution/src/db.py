"""Cấu hình kết nối cơ sở dữ liệu."""
import pathlib
import tomllib

CONFIG = pathlib.Path(__file__).resolve().parent.parent / "config" / "db.toml"


def dsn():
    c = tomllib.loads(CONFIG.read_text(encoding="utf-8"))["db"]
    return f"postgresql://{c['user']}@{c['host']}:{c['port']}/{c['name']}"
