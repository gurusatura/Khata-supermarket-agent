import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(line_buffering=True)

from agent.harness import run_agent

CHAT_A = "concurrent_chat_A"
CHAT_B = "concurrent_chat_B"

def test_concurrent_billing():
    print("TEST: Concurrent Billing (Per-Chat Memory Scoping)")
    
    # Cleanup any stale state
    from services.db import get_connection
    from services.memory import set_preference
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sale_items WHERE sale_id IN (SELECT id FROM sales WHERE telegram_chat_id IN (%s, %s));", (CHAT_A, CHAT_B))
            cur.execute("DELETE FROM sales WHERE telegram_chat_id IN (%s, %s) AND status='draft';", (CHAT_A, CHAT_B))
            conn.commit()
    set_preference(f"active_sale_id:{CHAT_A}", None)
    set_preference(f"active_sale_id:{CHAT_B}", None)

    history_A = []
    history_B = []

    print("\n--- TURN 1 ---")
    print("[CHAT A] Starting bill...")
    reply_A, history_A = run_agent("Start a cash bill for walk-in customer", CHAT_A, history_A)
    print(f"Agent A: {reply_A}")

    print("[CHAT B] Starting bill...")
    reply_B, history_B = run_agent("Start a cash bill for walk-in customer", CHAT_B, history_B)
    print(f"Agent B: {reply_B}")

    print("\n--- TURN 2 ---")
    print("[CHAT A] Adding 1kg Toor Dal...")
    reply_A, history_A = run_agent("Add 1 kg of Toor Dal", CHAT_A, history_A)
    print(f"Agent A: {reply_A}")

    print("[CHAT B] Adding 2 packets of Maggi...")
    reply_B, history_B = run_agent("Add 2 packets of Maggi", CHAT_B, history_B)
    print(f"Agent B: {reply_B}")

    print("\n--- TURN 3 ---")
    print("[CHAT A] Finalizing...")
    reply_A, history_A = run_agent("That's all, finalize the bill", CHAT_A, history_A)
    print(f"Agent A: {reply_A}")
    
    print("[CHAT B] Finalizing...")
    reply_B, history_B = run_agent("That's all, finalize the bill", CHAT_B, history_B)
    print(f"Agent B: {reply_B}")

    # Validation
    assert "155" in reply_A, f"Chat A should total 155.0 (1kg Toor Dal). Got: {reply_A}"
    assert "28" in reply_B, f"Chat B should total 28.0 (2x Maggi @ 14.0). Got: {reply_B}"
    
    print("\nPASSED: Both chats maintained isolated states and calculated correct independent totals.")

if __name__ == "__main__":
    try:
        test_concurrent_billing()
    except Exception as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)
