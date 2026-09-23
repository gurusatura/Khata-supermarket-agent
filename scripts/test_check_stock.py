import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.db import get_connection
from services.inventory import check_stock

def run_test():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM products WHERE name LIKE '%Maggi%' LIMIT 1;")
            maggi_id, maggi_name = cur.fetchone()

    print(f"📦 Checking stock for {maggi_name}...")
    qty = check_stock(maggi_id)
    print(f"✅ Result: {qty} units available")

if __name__ == "__main__":
    run_test()
