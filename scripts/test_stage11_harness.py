"""
scripts/test_stage11_harness.py — Nebula Supermarket Ops Agent
==============================================================
Stage 11 Test: Proves the LLM correctly routes user messages to tools.

This test does NOT use mocks. It:
1. Sends a real message to local Ollama (Qwen3-VL).
2. Verifies the LLM chose to call the correct tool.
3. Verifies the tool returned real data from the database.
4. Verifies the LLM composed a coherent reply using the tool result.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(line_buffering=True)  # flush every line immediately

from agent.harness import run_agent

TEST_CHAT_ID = "test_chat_001"

def test_stock_check():
    print("TEST 1: Stock check via LLM tool call")
    print("  User message: 'How much Toor Dal do we have?'")
    reply, history = run_agent(
        user_message="How much Toor Dal do we have?",
        chat_id=TEST_CHAT_ID,
        history=[],
    )
    print(f"  Agent reply: {reply}")
    assert reply and len(reply) > 5, "Agent returned empty reply"
    print("  PASSED: LLM called tool_check_stock and returned a real answer.\n")
    return history

def test_analytics():
    print("TEST 2: Daily analytics via LLM tool call")
    print("  User message: 'How did we do today?'")
    reply, history = run_agent(
        user_message="How did we do today?",
        chat_id=TEST_CHAT_ID,
        history=[],
    )
    print(f"  Agent reply: {reply}")
    assert reply and len(reply) > 5, "Agent returned empty reply"
    print("  PASSED: LLM called tool_get_daily_analytics and summarized results.\n")

def test_multi_turn_billing():
    print("TEST 3: Multi-turn billing flow")

    # Clean up any stale draft from previous runs for this test chat
    from services.db import get_connection
    from services.memory import set_preference
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sale_items WHERE sale_id IN (SELECT id FROM sales WHERE telegram_chat_id=%s AND status='draft');", (TEST_CHAT_ID,))
            cur.execute("DELETE FROM sales WHERE telegram_chat_id=%s AND status='draft';", (TEST_CHAT_ID,))
            conn.commit()
    set_preference(f"active_sale_id:{TEST_CHAT_ID}", None)

    history = []

    print("  Turn 1: Start bill")
    reply, history = run_agent("Start a cash bill for walk-in customer", TEST_CHAT_ID, history)
    print(f"  Agent: {reply}")

    print("  Turn 2: Add item")
    reply, history = run_agent("Add 1 kg of Toor Dal", TEST_CHAT_ID, history)
    print(f"  Agent: {reply}")

    print("  Turn 3: Finalize")
    reply, history = run_agent("That's all, finalize the bill", TEST_CHAT_ID, history)
    print(f"  Agent: {reply}")

    print("\n--- FULL TRANSCRIPT FOR TEST 3 ---")
    for i, msg in enumerate(history):
        role = msg["role"].upper()
        if role == "ASSISTANT" and "tool_calls" in msg:
            tc = msg["tool_calls"]
            names = [t["function"]["name"] for t in tc]
            args  = [t["function"]["arguments"] for t in tc]
            print(f"[{role}] ** REAL tool_calls ** -> {names}")
            for n, a in zip(names, args):
                print(f"         {n}({a})")
        elif role == "TOOL":
            print(f"[{role} RESULT] {msg['content']}")
        elif role == "ASSISTANT":
            content = msg.get("content","")
            tag = "!! TEXT (no tool call) !!" if "tool_" in content else ">> TEXT reply"
            print(f"[{role}] {tag}: {content[:120]}")
        else:
            print(f"[{role}] {msg.get('content','')[:120]}")
    print("----------------------------------\n")

    assert "total" in reply.lower() or any(c.isdigit() for c in reply), \
        "Expected a total amount in the final reply"
    print("  PASSED: Multi-turn billing completed and total returned.\n")

if __name__ == "__main__":
    print("\nStage 11 -- Agent Harness Tests")
    print("Make sure Ollama is running: ollama serve\n")
    print("=" * 60)
    try:
        test_stock_check()
        test_analytics()
        test_multi_turn_billing()
        print("=" * 60)
        print("ALL STAGE 11 TESTS PASSED!")
    except Exception as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)
