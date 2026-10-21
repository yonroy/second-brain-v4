"""Đồng bộ danh mục sản phẩm từ nhà cung cấp (job chạy mỗi 15 phút, có retry)."""


def sync_products(api, conn):
    cursor = None
    while True:
        page = api.fetch(cursor)
        conn.executemany("INSERT INTO products(sku, price) VALUES (:sku, :price) "
                         "ON CONFLICT(sku) DO UPDATE SET price = excluded.price", page["items"])
        if not page.get("has_more"):
            break
        cursor = page["next"]
    conn.commit()
