from src.coupons import COUPONS


def new_cart():
    return {"items": [], "coupon": None}


def add_item(cart, sku, price, qty=1):
    cart["items"].append({"sku": sku, "price": price, "qty": qty})


def apply_coupon(cart, code):
    if code not in COUPONS:
        return False
    cart["coupon"] = code
    return True
