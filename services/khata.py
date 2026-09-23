from services.db import get_connection

def get_khata_balance(customer_id: str) -> float:
    """Returns the current credit balance for a customer."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT balance FROM khata_accounts WHERE customer_id = %s;", (customer_id,))
            res = cur.fetchone()
            return float(res[0]) if res else 0.0

def record_payment(customer_id: str, amount: float, note: str = "Payment received") -> float:
    """Records a customer payment and deducts it from their khata balance."""
    if amount <= 0:
        raise ValueError("Payment amount must be strictly positive.")
        
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Add to khata_txns
            cur.execute("""
                INSERT INTO khata_txns (customer_id, txn_type, amount, note)
                VALUES (%s, 'payment', %s, %s);
            """, (customer_id, amount, note))
            
            # Deduct from khata_accounts balance
            cur.execute("""
                UPDATE khata_accounts SET balance = balance - %s, updated_at = NOW()
                WHERE customer_id = %s RETURNING balance;
            """, (amount, customer_id))
            res = cur.fetchone()
            if not res:
                raise ValueError("Customer khata account not found.")
                
            new_bal = res[0]
            conn.commit()
            return float(new_bal)
