from datetime import datetime


def parse_date(s):
    return datetime.strptime(s.strip().replace("-", "/"), "%d/%m/%Y").date()
