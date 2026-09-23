from datetime import datetime, timedelta
from services.db import get_connection

def predict_demand(product_id: str, historical_days: int = 30, forecast_days: int = 7) -> dict:
    """
    Predicts demand for a product based on a simple historical moving average.
    Separates the pure forecast demand from the recommended reorder quantity.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Get total units sold in the historical period
            cur.execute("""
                SELECT SUM(ABS(quantity)) 
                FROM inventory_transactions 
                WHERE product_id = %s 
                  AND txn_type = 'sale' 
                  AND created_at >= NOW() - CAST(%s AS INTERVAL);
            """, (product_id, f"{historical_days} days"))
            
            res = cur.fetchone()
            total_sold = float(res[0]) if res and res[0] else 0.0
            
            # 2. Get current stock
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s;", (product_id,))
            stock_res = cur.fetchone()
            current_stock = float(stock_res[0]) if stock_res else 0.0
            
            # 3. Calculate metrics
            average_daily_demand = total_sold / historical_days if historical_days > 0 else 0.0
            forecast_demand = average_daily_demand * forecast_days
            
            # 4. Calculate reorder recommendation
            # If we already have more stock than the forecast, we need 0.
            recommended_reorder = max(0.0, forecast_demand - current_stock)
            
            return {
                "product_id": str(product_id),
                "historical_days": historical_days,
                "total_units_sold": total_sold,
                "average_daily_demand": round(average_daily_demand, 2),
                "forecast_days": forecast_days,
                "forecast_demand": round(forecast_demand, 2),
                "current_stock": round(current_stock, 2),
                "recommended_reorder_qty": round(recommended_reorder, 2)
            }
