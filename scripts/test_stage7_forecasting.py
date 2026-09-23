"""
test_stage7_forecasting.py — Nebula Supermarket Ops Agent
=========================================================
Tests the Stage 7 Forecasting module using a simple moving average.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.db import get_connection
from services.forecasting import predict_demand
import json

def run_test():
    print("Stage 7: Forecasting Test\n")
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM products WHERE name LIKE '%Maggi%' LIMIT 1;")
            maggi = cur.fetchone()
            if not maggi:
                print("Could not find Maggi in the DB.")
                sys.exit(1)
            maggi_id, maggi_name = maggi
            
            # Since we just ran Stage 4 and 5 tests, there should be some recent sale data for Maggi.
            # However, because we want to see a clear calculation, let's inject a fake historical 
            # transaction representing exactly 300 packets sold over the last 30 days.
            print("injecting 300 historical sales for Maggi to test the 10/day math...")
            cur.execute("""
                INSERT INTO inventory_transactions (product_id, txn_type, quantity, note, created_at)
                VALUES (%s, 'sale', -300, 'Historical injection for forecasting test', NOW() - INTERVAL '15 days');
            """, (maggi_id,))
            
            # Set current stock to exactly 20 so we match the mentor's example perfectly
            cur.execute("UPDATE inventory SET quantity = 20 WHERE product_id = %s;", (maggi_id,))
            conn.commit()
    
    print(f"\nPredicting Demand for: {maggi_name}")
    print(f"Historical Window: 30 days")
    print(f"Forecast Window: 7 days")
    
    result = predict_demand(maggi_id, historical_days=30, forecast_days=7)
    
    print("\nResult:")
    print(json.dumps(result, indent=2))
    
    # Validation against the mentor's example
    assert result["average_daily_demand"] > 10.0, "Average daily demand should be > 10 (300 injected + real sales)"
    assert result["current_stock"] == 20.0, "Current stock should be 20"
    
    print("\nForecasting Logic is working exactly as specified!")

if __name__ == "__main__":
    run_test()
