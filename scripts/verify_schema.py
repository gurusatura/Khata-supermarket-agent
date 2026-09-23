"""
verify_schema.py — Nebula Supermarket Ops Agent
================================================
Connects to Supabase PostgreSQL using DATABASE_URL from .env and:
  1. Checks all 10 expected tables exist
  2. Checks the invoice_number_seq sequence exists
  3. Checks all indexes exist
  4. Runs the oversell-guard test:
       - inserts a temporary test product
       - tries to insert inventory with quantity = -1 (must be rejected)
       - confirms the CHECK constraint error fires
       - cleans up the test product

Run this from the project root:
    python scripts/verify_schema.py
"""

import os
import sys
# pyrefly: ignore [missing-import]
import psycopg
from dotenv import load_dotenv

# ── Load .env ──────────────────────────────────────────────────────────────────
load_dotenv()  # reads d:\supermarket_nebula\.env into environment variables

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL is not set in your .env file.")
    print("Open .env and paste your Supabase connection string after DATABASE_URL=")
    sys.exit(1)

# ── Connect ───────────────────────────────────────────────────────────────────
print("Connecting to Supabase...", end=" ")
try:
    conn = psycopg.connect(DATABASE_URL)
    conn.autocommit = False          # we'll manage transactions manually
    cur = conn.cursor()
    print("OK\n")
except Exception as e:
    print(f"\nFAILED — could not connect.\nError: {e}")
    sys.exit(1)

PASS = "✅"
FAIL = "❌"

# ── 1. Table list ─────────────────────────────────────────────────────────────
print("─" * 60)
print("CHECK 1: All 10 tables exist")
print("─" * 60)

EXPECTED_TABLES = sorted([
    "customers", "inventory", "inventory_transactions",
    "khata_accounts", "khata_txns", "preferences",
    "products", "request_log", "sale_items", "sales",
])

cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name;
""")
found_tables = sorted([row[0] for row in cur.fetchall()])

for t in EXPECTED_TABLES:
    status = PASS if t in found_tables else FAIL
    print(f"  {status}  {t}")

extra = [t for t in found_tables if t not in EXPECTED_TABLES]
if extra:
    print(f"\n  (Extra tables found — not expected but not a problem: {extra})")
print()

# ── 2. Sequence check ─────────────────────────────────────────────────────────
print("─" * 60)
print("CHECK 2: invoice_number_seq sequence exists")
print("─" * 60)

cur.execute("""
    SELECT sequence_name
    FROM information_schema.sequences
    WHERE sequence_schema = 'public';
""")
sequences = [row[0] for row in cur.fetchall()]
if "invoice_number_seq" in sequences:
    print(f"  {PASS}  invoice_number_seq found")
else:
    print(f"  {FAIL}  invoice_number_seq MISSING — re-run the schema SQL")
print()

# ── 3. Index check ────────────────────────────────────────────────────────────
print("─" * 60)
print("CHECK 3: Critical indexes exist")
print("─" * 60)

EXPECTED_INDEXES = [
    "idx_products_name_active",
    "idx_customers_phone",
    "idx_sales_one_draft_per_chat",
    "idx_sales_chat_status",
    "idx_sales_request_id",
    "idx_sales_finalized_at",
    "idx_sale_items_sale_id",
    "idx_inv_txns_product_created",
    "idx_khata_txns_customer",
]

cur.execute("""
    SELECT indexname
    FROM pg_indexes
    WHERE schemaname = 'public';
""")
found_indexes = [row[0] for row in cur.fetchall()]

for idx in EXPECTED_INDEXES:
    status = PASS if idx in found_indexes else FAIL
    print(f"  {status}  {idx}")
print()

# ── 4. Oversell guard test ────────────────────────────────────────────────────
print("─" * 60)
print("CHECK 4: Oversell guard — CHECK (quantity >= 0) fires at DB level")
print("─" * 60)

try:
    # Step 4a: insert a temporary test product
    cur.execute("""
        INSERT INTO products (name, unit_type, cost_price, sell_price, gst_rate, hsn_code)
        VALUES ('__test__', 'packet', 10, 15, 5, '1902')
        RETURNING id;
    """)
    test_product_id = cur.fetchone()[0]
    print(f"  Test product inserted, id = {test_product_id}")

    # Step 4b: attempt to insert inventory with quantity = -1
    # This MUST fail. We expect psycopg2 to raise an exception here.
    print("  Attempting INSERT with quantity = -1 (expecting DB rejection)...")
    try:
        cur.execute("""
            INSERT INTO inventory (product_id, quantity)
            VALUES (%s, -1);
        """, (test_product_id,))
        conn.commit()
        # If we reach this line, the constraint did NOT fire — that's a problem
        print(f"  {FAIL}  CONSTRAINT DID NOT FIRE — negative quantity was accepted!")
        print("       The oversell guard is NOT in place. Re-check the schema SQL.")

    except psycopg.errors.CheckViolation as e:
        # This is the expected path — the DB rejected the negative quantity
        conn.rollback()  # roll back the failed transaction so the connection stays usable
        print(f"  {PASS}  DB correctly rejected quantity = -1")
        print(f"         PostgreSQL error: {e.pgerror.strip()}")

    except Exception as e:
        conn.rollback()
        print(f"  {FAIL}  Unexpected error (not a CheckViolation): {e}")

    # Step 4c: clean up — delete the test product
    # This works because inventory row was never committed (rolled back above)
    cur.execute("DELETE FROM products WHERE name = '__test__';")
    conn.commit()
    print("  Test product cleaned up.\n")

except Exception as e:
    conn.rollback()
    print(f"  {FAIL}  Error during oversell test setup: {e}\n")

# ── Done ──────────────────────────────────────────────────────────────────────
cur.close()
conn.close()
print("─" * 60)
print("Verification complete. Review any ❌ items above before proceeding.")
print("─" * 60)
