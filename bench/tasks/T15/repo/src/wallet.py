def withdraw(wallets: dict, wid: str, amount: int) -> None:
    if wallets[wid] < amount:
        raise ValueError("insufficient funds")
    wallets[wid] -= amount
