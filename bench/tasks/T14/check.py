import json
import subprocess
import sys

CASES = [(["Bình", "Đức", "An", "Em", "Dũng"], ["An", "Bình", "Dũng", "Đức", "Em"]),
         (["Ơn", "On", "Ôn"], ["On", "Ôn", "Ơn"]),
         (["ân", "an", "ăn"], ["an", "ăn", "ân"]),
         (["bình", "An"], ["An", "bình"]),
         (["Ưng", "Uyên", "Vy"], ["Uyên", "Ưng", "Vy"])]


def check(work, events):
    code = ("import json,sys; sys.stdout.reconfigure(encoding='utf-8'); from src.customers import sort_customers as s; "
            "print(json.dumps([s(list(c)) for c in json.loads(sys.argv[1])], ensure_ascii=False))")
    r = subprocess.run([sys.executable, "-c", code, json.dumps([c for c, _ in CASES], ensure_ascii=False)], cwd=work,
                       capture_output=True, text=True, timeout=60, encoding="utf-8")
    try:
        got = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"pass": False, "trap_avoided": None, "notes": (r.stdout + r.stderr)[-300:]}
    return {"pass": got == [w for _, w in CASES], "trap_avoided": None, "notes": json.dumps(got, ensure_ascii=False)[:300]}
