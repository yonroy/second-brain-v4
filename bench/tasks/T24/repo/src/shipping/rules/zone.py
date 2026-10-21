ZONES = {"HN": 0, "HCM": 0, "other": 15000}


def zone_fee(zone):
    return ZONES.get(zone, ZONES["other"])
