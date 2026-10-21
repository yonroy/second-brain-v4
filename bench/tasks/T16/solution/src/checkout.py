from decimal import ROUND_HALF_UP, Decimal

from src.coupons import COUPONS


def checkout(cart):
    total = sum(i["price"] * i["qty"] for i in cart["items"])
    code = cart.get("coupon")
    if code:
        value = Decimal(total) * (100 - COUPONS[code]) / 100
        total = int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return {"total": total, "items": len(cart["items"]), "coupon": code}
