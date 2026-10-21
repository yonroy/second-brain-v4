def checkout(cart):
    total = sum(i["price"] * i["qty"] for i in cart["items"])
    return {"total": total, "items": len(cart["items"])}
