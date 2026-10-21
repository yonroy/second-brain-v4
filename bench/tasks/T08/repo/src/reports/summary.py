from src import users


def owner_names(ids):
    return [users.get_usr(i)["name"] for i in ids]
