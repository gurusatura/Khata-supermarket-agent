"""
test_receive.py — Nebula Supermarket Ops Agent
==============================================
Directly tests the receive_stock business service.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.db import get_connection
from services.inventory import receive_stock

def run_test():
    # 1. Grab the ID of Maggi from the database
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM products WHERE name LIKE '%Maggi%' LIMIT 1;")
            result = cur.fetchone()
            if not result:
                print("Could not find Maggi in the database. Did you run the seed script?")
                sys.exit(1)
            maggi_id, maggi_name = result
            
            # Check current stock
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s;", (maggi_id,))
            current_qty = cur.fetchone()[0]
            print(f"Current stock for {maggi_name}: {current_qty}")

    # 2. Call our pure business logic function
    print("\n📦 Calling receive_stock(quantity=20)...")
    try:
        res = receive_stock(maggi_id, 20.0, "Supplier delivery test")
        print("✅ Success!")
        print(f"   Added: {res['added']}")
        print(f"   New Total: {res['new_total']}")
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    run_test()
