from decimal import ROUND_HALF_UP, Decimal


def add(a: int, b: int) -> int:
    return a + b


def apply_discount(amount: int, percent) -> int:
    value = Decimal(amount) * (Decimal(100) - Decimal(str(percent))) / Decimal(100)
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))
