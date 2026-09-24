"""
agent/executor.py — Nebula Supermarket Ops Agent
=================================================
Stage 11: Tool Executor

This module is the bridge between tool *names* (strings the LLM uses)
and our actual Python service functions.

When the LLM says "call tool_check_stock with product_name='Maggi'",
the harness calls execute_tool("tool_check_stock", {"product_name": "Maggi"}, chat_id).
This function then calls the real services/inventory.check_stock() function.
"""

from datetime import date as date_type

# ── Import all service functions ──────────────────────────────
from services.inventory  import check_stock, receive_stock
from services.sales      import draft_sale, add_item_to_sale, finalize_sale
from services.khata      import get_khata_balance, record_payment
from services.analytics  import get_daily_sales
from services.documents  import generate_invoice
from services.db         import get_connection


def _find_product_id(product_name: str) -> str:
    """Helper: resolve a product name to its UUID from the DB."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM products WHERE name ILIKE %s LIMIT 1;",
                (f"%{product_name}%",)
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Product not found: '{product_name}'")
            return str(row[0])


def _find_customer_id(customer_name: str) -> str | None:
    """Helper: resolve customer name to UUID. Returns None for walk-in."""
    if "walk" in customer_name.lower() or customer_name.strip() == "":
        return None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM customers WHERE name ILIKE %s LIMIT 1;",
                (f"%{customer_name}%",)
            )
            row = cur.fetchone()
            return str(row[0]) if row else None


def _remove_item_from_sale(sale_id: str, product_name: str) -> dict:
    """Remove an item line from a draft sale by product name."""
    product_id = _find_product_id(product_name)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM sale_items WHERE sale_id = %s AND product_id = %s;",
                (sale_id, product_id)
            )
            if cur.rowcount == 0:
                return {"error": f"'{product_name}' was not found in this bill."}
            conn.commit()
    return {"status": "removed", "product": product_name, "sale_id": sale_id}


# ─────────────────────────────────────────────────────────────
# MAIN DISPATCHER
# ─────────────────────────────────────────────────────────────

def execute_tool(tool_name: str, args: dict, chat_id: str) -> dict:
    """
    Dispatch a tool call from the LLM to the correct service function.
    Always returns a dict so the LLM can read the result as JSON.
    """
    try:
        if tool_name == "tool_check_stock":
            product_id = _find_product_id(args["product_name"])
            qty = check_stock(product_id)
            return {"product": args["product_name"], "quantity": qty}

        elif tool_name == "tool_receive_stock":
            product_id = _find_product_id(args["product_name"])
            receive_stock(
                product_id=product_id,
                quantity=args["quantity"],
                cost_price=args["cost_price"],
                sell_price=args["sell_price"],
            )
            return {"status": "received", "product": args["product_name"], "quantity": args["quantity"]}

        elif tool_name == "tool_draft_sale":
            customer_id = _find_customer_id(args.get("customer_name", "Walk-in Customer"))
            sale_id = draft_sale(
                telegram_chat_id=chat_id,
                customer_id=customer_id,
            )
            return {"status": "draft_created", "sale_id": str(sale_id)}

        elif tool_name == "tool_add_item":
            product_id = _find_product_id(args["product_name"])
            add_item_to_sale(
                sale_id=args["sale_id"],
                product_id=product_id,
                quantity=args["quantity"],
            )
            return {"status": "item_added", "product": args["product_name"], "quantity": args["quantity"]}

        elif tool_name == "tool_remove_item":
            return _remove_item_from_sale(args["sale_id"], args["product_name"])

        elif tool_name == "tool_finalize_sale":
            payment_mode = args.get("payment_mode", "cash").lower()  # DB requires lowercase
            total = finalize_sale(
                sale_id=args["sale_id"],
                payment_mode=payment_mode,
                request_id=args["sale_id"],  # reuse sale_id as idempotency key
            )
            return {"status": "finalized", "grand_total": total, "sale_id": args["sale_id"]}

        elif tool_name == "tool_check_khata":
            customer_id = _find_customer_id(args["customer_name"])
            if not customer_id:
                return {"error": "Walk-in customers do not have a khata account."}
            balance = get_khata_balance(customer_id)
            return {"customer": args["customer_name"], "balance": balance}

        elif tool_name == "tool_record_khata_payment":
            customer_id = _find_customer_id(args["customer_name"])
            if not customer_id:
                return {"error": "Walk-in customers do not have a khata account."}
            record_payment(customer_id=customer_id, amount=args["amount"])
            return {"status": "payment_recorded", "customer": args["customer_name"], "amount": args["amount"]}

        elif tool_name == "tool_get_daily_analytics":
            raw_date = args.get("date")
            if raw_date:
                d = date_type.fromisoformat(raw_date)
            else:
                d = date_type.today()  # default to today when not specified
            result = get_daily_sales(d)
            return result

        elif tool_name == "tool_generate_invoice":
            path = generate_invoice(args["sale_id"])
            return {"status": "generated", "file_path": path}

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        return {"error": str(e)}
