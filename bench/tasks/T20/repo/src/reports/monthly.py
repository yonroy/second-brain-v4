from src.tax import tax_rate as _tr


def rate_table(cats):
    return {c: _tr(c) for c in cats}
