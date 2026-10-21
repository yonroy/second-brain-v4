import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def top_customers(conn):
    sql = (ROOT / "sql" / "reports" / "top_customers.sql").read_text(encoding="utf-8")
    cols = json.loads((ROOT / "dashboards" / "sales.json").read_text(encoding="utf-8"))["columns"]
    cur = conn.execute(sql)
    names = [d[0] for d in cur.description]
    return [{c: row[names.index(c)] for c in cols} for row in cur.fetchall()]
