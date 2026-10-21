import re


def _normalize_phone(p):
    p = re.sub(r"[\s.-]", "", p)
    if p.startswith("+84"):
        p = "0" + p[3:]
    elif p.startswith("84") and len(p) == 11:
        p = "0" + p[2:]
    return p


def register(phone):
    return {"phone": _normalize_phone(phone)}
