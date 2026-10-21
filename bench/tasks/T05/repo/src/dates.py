from datetime import datetime


def parse_date(s):
    return datetime.strptime(s.strip(), "%d/%m/%Y").date()
