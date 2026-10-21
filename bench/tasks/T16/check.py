import json
import subprocess
import sys

CODE = r"""
import json
from src.cart import new_cart, add_item, apply_coupon
from src.checkout import checkout
out = []
c = new_cart()
for s in "abc":
    add_item(c, s, 335)
out.append(apply_coupon(c, "SALE10")); apply_coupon(c, "SALE10")
o = checkout(c); out.append([o["total"], type(o["total"]).__name__, o.get("coupon")])
apply_coupon(c, "VIP25"); o = checkout(c); out.append([o["total"], o.get("coupon")])
d = new_cart(); add_item(d, "x", 1005)
out.append(apply_coupon(d, "NOPE")); o = checkout(d); out.append([o["total"], o.get("coupon")])
e = new_cart(); add_item(e, "y", 15); apply_coupon(e, "VIP25"); out.append(checkout(e)["total"])
print(json.dumps(out))
"""
WANT = [True, [905, "int", "SALE10"], [754, "VIP25"], False, [1005, None], 11]


def check(work, events):
    r = subprocess.run([sys.executable, "-c", CODE], cwd=work, capture_output=True, text=True, timeout=60)
    try:
        got = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"pass": False, "trap_avoided": False, "notes": (r.stdout + r.stderr)[-300:]}
    return {"pass": got == WANT, "trap_avoided": len(got) > 1 and got[1][0] == 905, "notes": json.dumps(got)[:300]}
