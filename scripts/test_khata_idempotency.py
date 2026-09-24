import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(line_buffering=True)

from agent.harness import run_agent
from services.db import get_connection
from services.memory import set_preference
from agent.executor import execute_tool

TEST_CHAT = "khata_test_chat"

def print_transcript(turn_name, user_msg, agent_reply):
    print(f"\n[Turn: {turn_name}]")
    print(f"USER: {user_msg}")
    print(f"AGENT: {agent_reply}")

def test_khata_flow():
    print("============================================================")
    print("TEST 1: Khata End-to-End Flow")
    
    # 1. Setup: Ensure Ramesh exists
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM customers WHERE name = 'Ramesh' LIMIT 1;")
            row = cur.fetchone()
            if not row:
                cur.execute("INSERT INTO customers (name, phone) VALUES ('Ramesh', '9999999999') RETURNING id;")
                customer_id = cur.fetchone()[0]
                cur.execute("INSERT INTO khata_accounts (customer_id, balance) VALUES (%s, 0);", (customer_id,))
            else:
                customer_id = row[0]
                cur.execute("UPDATE khata_accounts SET balance = 0 WHERE customer_id = %s;", (customer_id,))
                cur.execute("DELETE FROM khata_txns WHERE customer_id = %s;", (customer_id,))
            
            # Clean up stale drafts
            cur.execute("DELETE FROM sale_items WHERE sale_id IN (SELECT id FROM sales WHERE telegram_chat_id=%s AND status='draft');", (TEST_CHAT,))
            cur.execute("DELETE FROM sales WHERE telegram_chat_id=%s AND status='draft';", (TEST_CHAT,))
            conn.commit()

    set_preference(f"active_sale_id:{TEST_CHAT}", None)
    history = []

    # Turn 1: Draft sale
    msg1 = "Start a khata bill for Ramesh"
    reply1, history = run_agent(msg1, TEST_CHAT, history)
    print_transcript("Start Khata Bill", msg1, reply1)

    # Turn 2: Add items
    msg2 = "Add 1 kg of Toor Dal"
    reply2, history = run_agent(msg2, TEST_CHAT, history)
    print_transcript("Add Item", msg2, reply2)

    # Turn 3: Finalize
    msg3 = "Finalize the bill"
    reply3, history = run_agent(msg3, TEST_CHAT, history)
    print_transcript("Finalize Bill", msg3, reply3)
    
    # Turn 4: Check Khata
    msg4 = "What is Ramesh's khata balance?"
    reply4, history = run_agent(msg4, TEST_CHAT, history)
    print_transcript("Check Balance", msg4, reply4)
    
    # Turn 5: Record Payment
    msg5 = "Ramesh just paid 50 rupees towards his khata"
    reply5, history = run_agent(msg5, TEST_CHAT, history)
    print_transcript("Record Payment", msg5, reply5)
    
    # Turn 6: Check Khata again
    msg6 = "Check Ramesh's balance again"
    reply6, history = run_agent(msg6, TEST_CHAT, history)
    print_transcript("Check Final Balance", msg6, reply6)

def test_idempotency():
    print("\n============================================================")
    print("TEST 2: Finalize Idempotency Check")
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM customers WHERE name = 'Ramesh' LIMIT 1;")
            customer_id = cur.fetchone()[0]
            # Clean up
            cur.execute("DELETE FROM sale_items WHERE sale_id IN (SELECT id FROM sales WHERE telegram_chat_id=%s AND status='draft');", (TEST_CHAT,))
            cur.execute("DELETE FROM sales WHERE telegram_chat_id=%s AND status='draft';", (TEST_CHAT,))
            conn.commit()
    
    set_preference(f"active_sale_id:{TEST_CHAT}", None)
    history = []
    
    # Draft and add item
    _, history = run_agent("Start a cash bill for Ramesh", TEST_CHAT, history)
    _, history = run_agent("Add 1 packet of Maggi", TEST_CHAT, history)
    
    # Get active sale ID to force duplicate execution
    from services.memory import get_preference
    sale_id = get_preference(f"active_sale_id:{TEST_CHAT}")
    
    print(f"\n[Idempotency] Active Sale ID: {sale_id}")
    print("[Idempotency] First finalize call...")
    res1 = execute_tool("tool_finalize_sale", {"sale_id": sale_id, "payment_mode": "cash"}, TEST_CHAT)
    print(f"Result 1: {res1}")
    
    print("[Idempotency] Second finalize call (simulate telegram retry)...")
    try:
        res2 = execute_tool("tool_finalize_sale", {"sale_id": sale_id, "payment_mode": "cash"}, TEST_CHAT)
        print(f"Result 2: {res2}")
    except Exception as e:
        print(f"Result 2 Exception: {e}")

if __name__ == "__main__":
    try:
        test_khata_flow()
        test_idempotency()
    except Exception as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)
