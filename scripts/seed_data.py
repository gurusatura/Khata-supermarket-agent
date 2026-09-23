"""
seed_data.py — Nebula Supermarket Ops Agent
===========================================
Injects realistic Indian Kirana products, initial inventory, and customers
into the Supabase database.

WARNING: This script clears ALL existing data from the main tables before inserting.
Do not run this on a production database!
"""

import os
import sys
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in .env")
    sys.exit(1)

# --- THE SEED DATA ---

PRODUCTS = [
    # name, unit_type, is_loose, cost, mrp, gst, hsn
    ("Maggi 2-Minute Noodles 70g", "packet", False, 12.00, 14.00, 12, "1902"),
    ("Aashirvaad Whole Wheat Atta 5kg", "packet", False, 220.00, 245.00, 5, "1101"),
    ("Tata Salt 1kg", "packet", False, 22.00, 28.00, 0, "2501"),
    ("Amul Butter 100g", "packet", False, 52.00, 58.00, 12, "0405"),
    ("Premium Sona Masoori Rice", "kg", True, 55.00, 65.00, 0, "1006"),
    ("Loose Sugar", "kg", True, 40.00, 44.00, 5, "1701"),
    ("Toor Dal (Pigeon Pea)", "kg", True, 130.00, 155.00, 0, "0713"),
]

CUSTOMERS = [
    # name, phone
    ("Ramesh Kumar", "9876543210"),
    ("Suresh Patel", "9123456780"),
    ("Priya Sharma", "9988776655")
]

print("Connecting to Supabase...")
try:
    conn = psycopg.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()
except Exception as e:
    print(f"FAILED to connect: {e}")
    sys.exit(1)

try:
    # 1. Clean out existing data
    print("Clearing existing data (TRUNCATE CASCADE)...")
    cur.execute("""
        TRUNCATE TABLE 
            customers, products, inventory, inventory_transactions, 
            sales, sale_items, khata_accounts, khata_txns, 
            preferences, request_log
        RESTART IDENTITY CASCADE;
    """)
    
    # 2. Insert Products & Inventory
    print("Inserting products and initial stock...")
    for p in PRODUCTS:
        name, unit, is_loose, cost, mrp, gst, hsn = p
        
        # Insert product
        cur.execute("""
            INSERT INTO products (name, unit_type, is_loose, cost_price, sell_price, gst_rate, hsn_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (name, unit, is_loose, cost, mrp, gst, hsn))
        product_id = cur.fetchone()[0]
        
        # Decide initial quantity (50 packets or 50 kg)
        initial_qty = 50.0 
        
        # Insert inventory
        cur.execute("""
            INSERT INTO inventory (product_id, quantity)
            VALUES (%s, %s);
        """, (product_id, initial_qty))
        
        # Log transaction
        cur.execute("""
            INSERT INTO inventory_transactions (product_id, txn_type, quantity, note)
            VALUES (%s, 'receive', %s, 'Initial system seed');
        """, (product_id, initial_qty))

    # 3. Insert Customers & Khata
    print("Inserting customers and khata accounts...")
    for c in CUSTOMERS:
        name, phone = c
        
        cur.execute("""
            INSERT INTO customers (name, phone)
            VALUES (%s, %s)
            RETURNING id;
        """, (name, phone))
        customer_id = cur.fetchone()[0]
        
        # Set zero balance for khata
        cur.execute("""
            INSERT INTO khata_accounts (customer_id, balance)
            VALUES (%s, 0.00);
        """, (customer_id,))

    conn.commit()
    print("\n✅ Seed data successfully injected!")
    print(f"   Added {len(PRODUCTS)} products (with 50 units stock each)")
    print(f"   Added {len(CUSTOMERS)} customers (with ₹0 khata balances)")

except Exception as e:
    conn.rollback()
    print(f"\n❌ FAILED during seed: {e}")

finally:
    cur.close()
    conn.close()
