from datetime import date
from services.db import get_connection

def get_daily_sales(target_date: date = None) -> dict:
    """Returns analytics and total revenue for a specific day."""
    if not target_date:
        target_date = date.today()
        
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    COUNT(id), 
                    SUM(grand_total),
                    SUM(CASE WHEN payment_mode = 'cash' THEN grand_total ELSE 0 END),
                    SUM(CASE WHEN payment_mode = 'upi' THEN grand_total ELSE 0 END),
                    SUM(CASE WHEN payment_mode = 'khata' THEN grand_total ELSE 0 END),
                    SUM(cgst_total + sgst_total)
                FROM sales
                WHERE status = 'finalized' AND DATE(finalized_at) = %s;
            """, (target_date,))
            res = cur.fetchone()
            return {
                "date": str(target_date),
                "total_bills": res[0] or 0,
                "revenue": float(res[1] or 0.0),
                "cash": float(res[2] or 0.0),
                "upi": float(res[3] or 0.0),
                "credit": float(res[4] or 0.0),
                "tax_collected": float(res[5] or 0.0)
            }
