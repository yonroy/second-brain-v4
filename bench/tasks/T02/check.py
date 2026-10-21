import json
import subprocess
import sys

CASES = [("Đường Phố Hà Nội", "duong-pho-ha-noi"), ("Xin chào,  thế giới!", "xin-chao-the-gioi"),
         ("  Bánh mì  ", "banh-mi"), ("ĐĂNG KÝ", "dang-ky")]


def check(work, events):
    code = ("import json,sys; sys.stdout.reconfigure(encoding='utf-8'); from src.text import slugify; "
            "print(json.dumps([slugify(a) for a in json.loads(sys.argv[1])]))")
    r = subprocess.run([sys.executable, "-c", code, json.dumps([a for a, _ in CASES])], cwd=work,
                       capture_output=True, text=True, timeout=60, encoding="utf-8")
    try:
        got = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"pass": False, "trap_avoided": False, "notes": (r.stdout + r.stderr)[-300:]}
    want = [b for _, b in CASES]
    return {"pass": got == want, "trap_avoided": got[0] == want[0] and got[3] == want[3],
            "notes": json.dumps(got, ensure_ascii=False)}
