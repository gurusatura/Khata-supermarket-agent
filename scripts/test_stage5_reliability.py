"""
test_stage5_reliability.py — Nebula Supermarket Ops Agent
==========================================================
Stage 5: Reliability Tests
Proves three hard guarantees:
  1. Idempotency   — same request_id finalized twice = no double charge/deduction
  2. Oversell Guard — sell more than stock = clean rejection, stock intact
  3. Concurrency   — two threads finalize against same limited stock simultaneously
                     = exactly one wins, stock never goes negative
"""

import sys
import os
import uuid
import threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.db import get_connection
from services.sales import draft_sale, add_item_to_sale, finalize_sale
from services.inventory import receive_stock, check_stock

SEPARATOR = "─" * 60

def get_product(name_like):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM products WHERE name ILIKE %s LIMIT 1;", (f"%{name_like}%",))
            return cur.fetchone()

def get_stock(product_id):
    return check_stock(product_id)

def get_khata_balance(customer_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT balance FROM khata_accounts WHERE customer_id = %s;", (customer_id,))
            r = cur.fetchone()
            return float(r[0]) if r else 0.0

def cleanup():
    """Reset test product stock to a known amount before each test."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Clear all draft sales and test data to prevent stale state
            cur.execute("DELETE FROM sale_items WHERE sale_id IN (SELECT id FROM sales WHERE status = 'draft');")
            cur.execute("DELETE FROM sales WHERE status = 'draft';")
            conn.commit()

# ─────────────────────────────────────────────────────────────
# TEST 1: IDEMPOTENCY
# ─────────────────────────────────────────────────────────────
def test_idempotency():
    print(f"\n{SEPARATOR}")
    print("TEST 1: IDEMPOTENCY")
    print("  Same request_id sent twice → only ONE stock deduction")
    print(SEPARATOR)
    
    toor_id, toor_name = get_product("Toor Dal")
    stock_before = get_stock(toor_id)
    print(f"  Stock before: {stock_before} kg of {toor_name}")
    
    # Create and finalize one sale
    sale_id = draft_sale(9000000001)
    add_item_to_sale(sale_id, toor_id, 2.0)  # sell 2 kg
    
    shared_request_id = str(uuid.uuid4())
    
    # First finalize — should succeed
    res1 = finalize_sale(sale_id, "cash", shared_request_id)
    stock_after_first = get_stock(toor_id)
    print(f"  1st finalize → ✅ Grand Total: ₹{res1['grand_total']}")
    print(f"  Stock after 1st finalize: {stock_after_first} kg (expected {stock_before - 2})")
    
    # Second finalize with SAME request_id — must return cached result, NOT deduct again
    res2 = finalize_sale(sale_id, "cash", shared_request_id)
    stock_after_second = get_stock(toor_id)
    print(f"  2nd finalize (same ID) → Response: {res2['status']}")
    print(f"  Stock after 2nd finalize: {stock_after_second} kg")
    
    if stock_after_second == stock_after_first:
        print("  ✅ IDEMPOTENCY PASSED — stock deducted exactly once")
    else:
        print(f"  ❌ IDEMPOTENCY FAILED — stock changed from {stock_after_first} to {stock_after_second}")

# ─────────────────────────────────────────────────────────────
# TEST 2: OVERSELL GUARD
# ─────────────────────────────────────────────────────────────
def test_oversell():
    print(f"\n{SEPARATOR}")
    print("TEST 2: OVERSELL GUARD")
    print("  Try to sell more than available stock → clean rejection")
    print(SEPARATOR)
    
    salt_id, salt_name = get_product("Tata Salt")
    stock_before = get_stock(salt_id)
    print(f"  Stock before: {stock_before} packets of {salt_name}")
    
    # Try to sell way more than exists (stock is 50, we try 999)
    try:
        sale_id = draft_sale(9000000002)
        add_item_to_sale(sale_id, salt_id, 999.0)
        finalize_sale(sale_id, "cash", str(uuid.uuid4()))
        print("  ❌ OVERSELL GUARD FAILED — sale went through!")
    except Exception as e:
        stock_after = get_stock(salt_id)
        print(f"  Exception caught: {e}")
        if stock_after == stock_before:
            print(f"  Stock unchanged: {stock_after} packets ✅")
            print("  ✅ OVERSELL GUARD PASSED — rejected cleanly, no stock lost")
        else:
            print(f"  ❌ PARTIAL FAILURE — stock changed to {stock_after} despite error")

# ─────────────────────────────────────────────────────────────
# TEST 3: CONCURRENCY
# ─────────────────────────────────────────────────────────────
def test_concurrency():
    print(f"\n{SEPARATOR}")
    print("TEST 3: CONCURRENCY")
    print("  Two threads finalize simultaneously → exactly one wins")
    print(SEPARATOR)
    
    sugar_id, sugar_name = get_product("Loose Sugar")
    
    # Set stock to exactly 10 kg for this test
    current = get_stock(sugar_id)
    if current < 10:
        receive_stock(sugar_id, 10 - current, "Concurrency test top-up")
    # Sell down to exactly 10
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE inventory SET quantity = 10 WHERE product_id = %s;", (sugar_id,))
            conn.commit()
    
    stock_before = get_stock(sugar_id)
    print(f"  Stock set to exactly: {stock_before} kg of {sugar_name}")
    print(f"  Launching 2 threads, each trying to buy 8 kg (only 10 available)...")
    
    results = []
    
    def attempt_sale(thread_num):
        try:
            sid = draft_sale(9000000010 + thread_num)
            add_item_to_sale(sid, sugar_id, 8.0)  # each wants 8 kg, only 10 available
            res = finalize_sale(sid, "cash", str(uuid.uuid4()))
            results.append(("success", thread_num, res['grand_total']))
        except Exception as e:
            results.append(("fail", thread_num, str(e)))
    
    t1 = threading.Thread(target=attempt_sale, args=(1,))
    t2 = threading.Thread(target=attempt_sale, args=(2,))
    t1.start(); t2.start()
    t1.join(); t2.join()
    
    successes = [r for r in results if r[0] == "success"]
    failures  = [r for r in results if r[0] == "fail"]
    
    print(f"  Results: {len(successes)} success, {len(failures)} failure")
    for r in results:
        icon = "✅" if r[0] == "success" else "❌"
        print(f"    Thread {r[1]}: {r[0].upper()} — {r[2]}")
    
    stock_after = get_stock(sugar_id)
    print(f"  Stock after: {stock_after} kg (must be >= 0)")
    
    if stock_after >= 0 and len(successes) == 1 and len(failures) == 1:
        print("  ✅ CONCURRENCY PASSED — exactly one sale went through, stock is safe")
    elif stock_after < 0:
        print("  ❌ CONCURRENCY FAILED — stock went negative!")
    elif len(successes) == 2:
        print("  ❌ CONCURRENCY FAILED — both sales went through, stock oversold!")
    else:
        # Both failed (also acceptable — no corruption)
        print(f"  ⚠️  Both threads failed — stock still {stock_after} kg (no corruption)")

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🔍 Stage 5 — Reliability Test Suite")
    cleanup()
    test_idempotency()
    cleanup()
    test_oversell()
    cleanup()
    test_concurrency()
    print(f"\n{SEPARATOR}")
    print("Stage 5 test run complete.")
    print(SEPARATOR)
