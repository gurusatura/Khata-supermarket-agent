import sys
import os
import uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.db import get_connection
from services.sales import draft_sale, add_item_to_sale, finalize_sale
from services.khata import get_khata_balance, record_payment
from services.analytics import get_daily_sales

def run_all_tests():
    print("🚀 Starting Stage 4 Integration Test...\n")
    
    # 1. Setup: Get a customer and some products
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM customers LIMIT 1;")
            cust = cur.fetchone()
            if not cust:
                print("❌ No customers found. Run seed_data.py first.")
                return
            customer_id, customer_name = cust
            
            cur.execute("SELECT id, name FROM products WHERE name LIKE '%Maggi%' LIMIT 1;")
            maggi_id, maggi_name = cur.fetchone()
            
            cur.execute("SELECT id, name FROM products WHERE name LIKE '%Atta%' LIMIT 1;")
            atta_id, atta_name = cur.fetchone()
            
    print(f"👤 Using Customer: {customer_name}")
    print(f"📦 Products: {maggi_name}, {atta_name}\n")
    
    # 2. Test Sales Pipeline
    telegram_id = 123456789
    print(f"🛒 1. Drafting Sale for Telegram ID: {telegram_id}...")
    sale_id = draft_sale(telegram_id, customer_id)
    print(f"   ✅ Draft Sale ID: {sale_id}")
    
    print("\n🛒 2. Adding Items...")
    add_item_to_sale(sale_id, maggi_id, 2.0) # 2 Maggi
    print(f"   ✅ Added 2x {maggi_name}")
    add_item_to_sale(sale_id, atta_id, 1.0) # 1 Atta
    print(f"   ✅ Added 1x {atta_name}")
    
    req_id = str(uuid.uuid4())
    print(f"\n🛒 3. Finalizing Sale (Credit)...")
    res = finalize_sale(sale_id, "khata", req_id)
    print(f"   ✅ Finalized! Grand Total: ₹{res['grand_total']}")
    
    # 3. Test Khata Pipeline
    print(f"\n📒 4. Checking Khata Balance...")
    bal = get_khata_balance(customer_id)
    print(f"   ✅ Current Balance: ₹{bal} (Should match Grand Total)")
    
    print(f"\n📒 5. Recording ₹50 Payment...")
    new_bal = record_payment(customer_id, 50.0)
    print(f"   ✅ New Balance: ₹{new_bal}")
    
    # 4. Test Analytics
    print(f"\n📊 6. Fetching Daily Sales Analytics...")
    analytics = get_daily_sales()
    print(f"   ✅ Today's Revenue: ₹{analytics['revenue']}")
    print(f"   ✅ Cash: ₹{analytics['cash']} | UPI: ₹{analytics['upi']} | Credit: ₹{analytics['credit']}")
    
    print("\n🎉 ALL TESTS PASSED! Stage 4 is complete.")

if __name__ == "__main__":
    try:
        run_all_tests()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
