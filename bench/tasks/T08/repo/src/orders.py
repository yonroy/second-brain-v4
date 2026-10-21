from src.users import get_usr


def order_owner(order):
    return get_usr(order["user_id"])["name"]
