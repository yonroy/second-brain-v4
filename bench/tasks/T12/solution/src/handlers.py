def handle_order_created(evt):
    return f"created:{evt['id']}"


def on_order_paid(evt):
    return f"paid:{evt['id']}"
