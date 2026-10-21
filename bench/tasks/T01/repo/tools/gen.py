import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def render(schema):
    lines = ["@dataclass", f"class {schema['name']}:"]
    for f in schema["fields"]:
        lines.append(f"    {f['name']}: {f['type']} = {f['default']!r}")
    return "\n".join(lines)


def main():
    blocks = [render(json.loads(p.read_text(encoding="utf-8")))
              for p in sorted((ROOT / "schema").glob("*.json"))]
    out = "from dataclasses import dataclass\n\n\n" + "\n\n\n".join(blocks) + "\n"
    (ROOT / "src" / "models.py").write_text(out, encoding="utf-8")


if __name__ == "__main__":
    main()
