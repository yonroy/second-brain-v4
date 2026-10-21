def new_cart():
    return {"items": [], "coupon": None}


def add_item(cart, sku, price, qty=1):
    cart["items"].append({"sku": sku, "price": price, "qty": qty})
