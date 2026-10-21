RATES = {"food": 0.05, "electronics": 0.10, "book": 0.0}
REGION = {"VN": 1.0, "US": 1.6}


def tax_rate(category, region):
    return RATES[category] * REGION[region]
