import subprocess
import sys

CODE = r"""
import sys, tempfile, os
from src.report import export_revenue_csv
p = os.path.join(tempfile.mkdtemp(), 'r.csv')
export_revenue_csv(p)
sys.stdout.write(open(p, 'rb').read().hex())
"""


def check(work, events):
    r = subprocess.run([sys.executable, "-c", CODE], cwd=work, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=60)
    try:
        raw = bytes.fromhex(r.stdout.strip())
    except ValueError:
        return {"pass": False, "trap_avoided": False, "notes": (r.stdout + r.stderr)[-300:]}
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig", errors="replace").replace("\r\n", "\n").strip().split("\n")
    data = [l for l in text[1:] if l.strip()]
    want = ["05/03/2026;Nguyễn Văn An;150000", '06/03/2026;"Công ty Bình Minh, chi nhánh 2";2750000',
            "06/03/2026;Công ty Bình Minh, chi nhánh 2;2750000", "07/03/2026;Đặng Thị Hoà;99000"]
    ok_rows = len(data) == 3 and data[0] == want[0] and data[1] in want[1:3] and data[2] == want[3]
    return {"pass": bom and ok_rows, "trap_avoided": bom, "notes": " | ".join(text[:4])[:300]}
