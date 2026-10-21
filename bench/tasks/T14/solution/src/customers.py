import unicodedata

ALPHABET = "aăâbcdđeêghiklmnoôơpqrstuưvxy"
MARKS = {"\u0306": "ă", "\u0302": "^", "\u031b": "+"}
TONES = {"\u0300", "\u0301", "\u0309", "\u0303", "\u0323"}


def _letter(ch):
    d = unicodedata.normalize("NFD", ch.lower())
    base, marks = d[0], [m for m in d[1:] if m not in TONES]
    if base == "đ":
        return "đ"
    if "\u0306" in marks and base == "a":
        return "ă"
    if "\u0302" in marks and base in "aeo":
        return {"a": "â", "e": "ê", "o": "ô"}[base]
    if "\u031b" in marks and base in "ou":
        return {"o": "ơ", "u": "ư"}[base]
    return base


def _key(name):
    out = []
    for ch in name:
        l = _letter(ch)
        out.append(ALPHABET.index(l) if l in ALPHABET else 100 + ord(l))
    return out


def sort_customers(names):
    return sorted(names, key=_key)
