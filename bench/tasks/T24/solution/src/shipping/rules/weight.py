HEAVY_FEE = 50000
LIGHT_FEE = 20000


def weight_fee(kg):
    if kg >= 5:
        return HEAVY_FEE
    return LIGHT_FEE
