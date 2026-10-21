import re


def _normalize_phone(p):
    p = re.sub(r"[\s.-]", "", p)
    if p.startswith("+84"):
        p = "0" + p[3:]
    elif p.startswith("84") and len(p) == 11:
        p = "0" + p[2:]
    return p


def register(phone):
    p = _normalize_phone(phone)
    if not (len(p) == 10 and p.isdigit()):
        raise ValueError(f"số điện thoại không hợp lệ: {phone!r}")
    return {"phone": p}
