from services.db import get_connection

def receive_stock(product_id: str, quantity: float, note: str = "Stock received") -> dict:
    """
    Adds quantity to the existing stock for a product and logs the transaction.
    """
    if quantity <= 0:
        raise ValueError("Receive quantity must be strictly greater than 0.")

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. UPSERT the inventory: 
            # If the product exists in inventory, add to it. If it doesn't, insert it.
            cur.execute("""
                INSERT INTO inventory (product_id, quantity)
                VALUES (%s, %s)
                ON CONFLICT (product_id) 
                DO UPDATE SET 
                    quantity = inventory.quantity + EXCLUDED.quantity,
                    updated_at = NOW()
                RETURNING quantity;
            """, (product_id, quantity))
            
            result = cur.fetchone()
            if not result:
                raise ValueError(f"Product {product_id} does not exist in products table.")
                
            new_total = result[0]

            # 2. Log the transaction for auditability
            cur.execute("""
                INSERT INTO inventory_transactions (product_id, txn_type, quantity, note)
                VALUES (%s, 'receive', %s, %s);
            """, (product_id, quantity, note))
            
            # The 'with' block for connection automatically commits if no exceptions occur,
            # but we explicitly commit here for clarity.
            conn.commit()

            return {
                "product_id": product_id,
                "added": quantity,
                "new_total": new_total
            }

def check_stock(product_id: str) -> float:
    """
    Returns the current available quantity for a product.
    Returns 0.0 if the product has no inventory record.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM inventory WHERE product_id = %s;", (product_id,))
            result = cur.fetchone()
            if result:
                return float(result[0])
            return 0.0
