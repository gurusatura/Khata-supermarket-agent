import json
from services.db import get_connection

def draft_sale(telegram_chat_id: str, customer_id: str = None) -> str:
    """Creates a new draft sale or returns existing draft for chat."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Check for existing draft to prevent duplicate open carts per chat
            cur.execute("""
                SELECT id FROM sales 
                WHERE telegram_chat_id = %s AND status = 'draft' 
                LIMIT 1;
            """, (telegram_chat_id,))
            res = cur.fetchone()
            if res:
                # Update customer_id if provided now
                if customer_id:
                    cur.execute("UPDATE sales SET customer_id = %s WHERE id = %s", (customer_id, res[0]))
                    conn.commit()
                return res[0]
            
            # Create new draft
            cur.execute("""
                INSERT INTO sales (telegram_chat_id, customer_id, status)
                VALUES (%s, %s, 'draft')
                RETURNING id;
            """, (telegram_chat_id, customer_id))
            sale_id = cur.fetchone()[0]
            conn.commit()
            return sale_id

def add_item_to_sale(sale_id: str, product_id: str, quantity: float) -> dict:
    """Adds an item, snapshots price, calculates accurate GST math."""
    if quantity <= 0:
        raise ValueError("Quantity must be strictly positive.")
        
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Grab current product details
            cur.execute("""
                SELECT cost_price, sell_price, hsn_code, gst_rate 
                FROM products WHERE id = %s;
            """, (product_id,))
            prod = cur.fetchone()
            if not prod:
                raise ValueError("Product not found.")
            cost_price, sell_price, hsn_code, gst_rate = prod
            
            # Reverse-calculate GST assuming sell_price is MRP (GST Inclusive)
            line_total = float(sell_price) * float(quantity)
            taxable_amount = line_total / (1 + (float(gst_rate) / 100))
            gst_total = line_total - taxable_amount
            cgst_amount = gst_total / 2
            sgst_amount = gst_total / 2
            
            cur.execute("""
                INSERT INTO sale_items (
                    sale_id, product_id, quantity, unit_price, cost_price, 
                    hsn_code, gst_rate, taxable_amount, cgst_amount, sgst_amount, line_total
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (sale_id, product_id, quantity, sell_price, cost_price, hsn_code, gst_rate, taxable_amount, cgst_amount, sgst_amount, line_total))
            
            conn.commit()
            return {"line_total": line_total}

def finalize_sale(sale_id: str, payment_mode: str, request_id: str) -> dict:
    """Finalizes sale, checks stock, deducts inventory, records khata. Atomically."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Idempotency check: did we already process this exact request?
            cur.execute("SELECT response FROM request_log WHERE request_id = %s;", (request_id,))
            res = cur.fetchone()
            if res:
                return res[0] # Return the cached JSON response
                
            # 2. Get sale details
            cur.execute("SELECT status, customer_id FROM sales WHERE id = %s FOR UPDATE;", (sale_id,))
            sale = cur.fetchone()
            if not sale:
                raise ValueError("Sale not found.")
            if sale[0] != 'draft':
                raise ValueError(f"Sale is already {sale[0]}")
            customer_id = sale[1]
            
            # Anonymous walk-in credit guardrail
            if payment_mode == 'khata' and not customer_id:
                raise ValueError("Anonymous walk-in customers cannot use credit.")
                
            # 3. Calculate totals from items
            cur.execute("""
                SELECT SUM(taxable_amount), SUM(cgst_amount), SUM(sgst_amount), SUM(line_total)
                FROM sale_items WHERE sale_id = %s;
            """, (sale_id,))
            totals = cur.fetchone()
            if not totals or totals[3] is None:
                raise ValueError("Cannot finalize an empty bill.")
            subtotal, cgst, sgst, grand_total = totals
            
            # 4. Inventory check and deduction
            cur.execute("SELECT product_id, quantity FROM sale_items WHERE sale_id = %s;", (sale_id,))
            items = cur.fetchall()
            for pid, qty in items:
                # Deduct inventory (CheckViolation handles oversell safely via Postgres constraint)
                cur.execute("""
                    UPDATE inventory 
                    SET quantity = quantity - %s, updated_at = NOW()
                    WHERE product_id = %s
                    RETURNING quantity;
                """, (qty, pid))
                if not cur.fetchone():
                    raise ValueError(f"Product {pid} not found in inventory.")
                
                # Log transaction
                cur.execute("""
                    INSERT INTO inventory_transactions (product_id, txn_type, quantity, sale_id, note)
                    VALUES (%s, 'sale', %s, %s, 'Sale finalize');
                """, (pid, -qty, sale_id))
                
            # 5. Update Sale
            cur.execute("""
                UPDATE sales SET
                    status = 'finalized', payment_mode = %s, subtotal = %s, 
                    cgst_total = %s, sgst_total = %s, grand_total = %s,
                    request_id = %s, finalized_at = NOW()
                WHERE id = %s;
            """, (payment_mode, subtotal, cgst, sgst, grand_total, request_id, sale_id))
            
            # 6. Update Khata if credit
            if payment_mode == 'khata':
                cur.execute("""
                    INSERT INTO khata_txns (customer_id, txn_type, amount, sale_id, note)
                    VALUES (%s, 'credit', %s, %s, 'Credit purchase');
                """, (customer_id, grand_total, sale_id))
                
                cur.execute("""
                    UPDATE khata_accounts SET balance = balance + %s, updated_at = NOW()
                    WHERE customer_id = %s;
                """, (grand_total, customer_id))
                
            response = {"status": "finalized", "grand_total": float(grand_total), "sale_id": str(sale_id)}
            
            # Log idempotency
            cur.execute("INSERT INTO request_log (request_id, response) VALUES (%s, %s);", (request_id, json.dumps(response)))
            
            conn.commit()
            return response
