def withdraw(wallets: dict, wid: str, amount: int) -> None:
    if wallets[wid] < amount:
        raise ValueError("insufficient funds")
    wallets[wid] -= amount


def _err(code):
    return {"ok": False, "error": code}


def transfer(wallets: dict, src: str, dst: str, amount: int) -> dict:
    if not isinstance(amount, int) or amount <= 0:
        return _err("INVALID_AMOUNT")
    if src == dst:
        return _err("SAME_WALLET")
    if src not in wallets or dst not in wallets:
        return _err("UNKNOWN_WALLET")
    if wallets[src] < amount:
        return _err("INSUFFICIENT_FUNDS")
    wallets[src] -= amount
    wallets[dst] += amount
    return {"ok": True, "error": None}
