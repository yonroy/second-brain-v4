from src.shipping.rules.weight import weight_fee
from src.shipping.rules.zone import zone_fee


def shipping_fee(order):
    return weight_fee(order["kg"]) + zone_fee(order["zone"])
