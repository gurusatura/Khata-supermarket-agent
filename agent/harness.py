"""
agent/harness.py — Nebula Supermarket Ops Agent
================================================
Stage 11: The Agent Run Loop

This is the "brain connector." It:
1. Receives a user message and a chat_id.
2. Sends the message + conversation history to the local Ollama (Qwen3-VL)
   via the OpenAI-compatible API.
3. If the LLM wants to call a tool, it executes the correct services/ function.
4. Persists the active sale_id per chat_id using Stage 10's memory module.
5. Loops until the LLM produces a plain text reply.

Architecture rule: this file only orchestrates. Business logic stays in services/.
"""

import json
import os
from openai import OpenAI

from agent.tools   import TOOL_DEFINITIONS
from agent.executor import execute_tool
from services.memory import get_preference, set_preference, get_all_preferences

# ─────────────────────────────────────────────────────────────
# Ollama client — OpenAI SDK pointed at local Ollama
# ─────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")

client = OpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key="ollama",          # Ollama ignores the key — required by SDK
)

# ─────────────────────────────────────────────────────────────
# System Prompt
# ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a billing assistant for Nebula Supermarket. You help the shopkeeper create bills, check inventory, and view analytics.

## CRITICAL RULE — READ THIS FIRST
If the user's message already contains the information a tool needs, call the tool IMMEDIATELY.
Do NOT ask clarifying questions for information the user has already provided.
Only ask if something is genuinely missing and cannot be inferred.

## Billing Workflow — follow this exactly, in order
1. Call `tool_draft_sale` to start a new bill. Use customer_name from the user's message (default: "Walk-in Customer").
2. Call `tool_add_item` for each product. You MUST pass the exact `sale_id` returned by step 1.
3. Call `tool_finalize_sale` to close the bill. You MUST pass the same `sale_id`.

## Rules
- NEVER make up a sale_id. Only use the one returned by `tool_draft_sale`.
- NEVER make up stock quantities or totals. Always call the tools.
- NEVER invent customer balances or payment records. ANY mention of a payment, balance check, or money changing hands MUST go through a tool call (`tool_check_khata` or `tool_record_khata_payment`). Do not perform mental math.
- NEVER ask for information the user already gave you in their message.

## One-shot examples
User: "Start a bill for Ramesh"
→ You call: tool_draft_sale(customer_name="Ramesh", payment_mode="CASH")   ← immediately, no text reply

User: "Add 2kg Toor Dal"
→ You call: tool_add_item(sale_id=<id from above>, product_name="Toor Dal", quantity=2)   ← immediately

User: "Done, finalize it"
→ You call: tool_finalize_sale(sale_id=<same id>)   ← immediately

User: "Ramesh paid 50 rupees"
→ You call: tool_record_khata_payment(customer_name="Ramesh", amount=50) ← immediately, no mental math
"""


def run_agent(user_message: str, chat_id: str, history: list) -> tuple[str, list]:
    """
    Run one turn of the agent loop.
    """
    # Recover active sale_id from persistent memory
    active_sale_key = f"active_sale_id:{chat_id}"
    recovered_sale_id = get_preference(active_sale_key)
    
    # Inject recovery context into system prompt
    system = SYSTEM_PROMPT
    if recovered_sale_id:
        system += f"\n\n[CRITICAL SYSTEM DATA]: There is currently an OPEN draft bill. The `sale_id` is: {recovered_sale_id}. You MUST pass this exact `sale_id` string to `tool_add_item`, `tool_remove_item`, or `tool_finalize_sale` when editing this bill."

    # Inject durable owner preferences from memory
    try:
        prefs = get_all_preferences()
        if prefs:
            prefs_lines = "\n".join([f"- {k}: {v}" for k, v in prefs.items()])
            system += f"\n\n[STORE OWNER PREFERENCES (DURABLE MEMORY)]:\n{prefs_lines}\nRespect these preferences by default unless overridden by the user."
    except Exception:
        pass

    # Build the messages list for this turn
    messages = [{"role": "system", "content": system}] + history
    messages.append({"role": "user", "content": user_message})

    # ── Agent Loop ────────────────────────────────────────────
    MAX_TOOL_ROUNDS = 5  # Safety cap
    DEBUG = os.getenv("AGENT_DEBUG", "1") == "1"  # on by default for now
    for round_num in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
        )

        msg = response.choices[0].message
        if DEBUG:
            print(f"  [DBG round={round_num}] finish_reason={response.choices[0].finish_reason} "
                  f"tool_calls={bool(msg.tool_calls)} content={repr((msg.content or '')[:80])}", flush=True)

        # ── Case 1: LLM wants to call tool(s) ────────────────
        if msg.tool_calls:
            # Append the assistant's tool-call request to history
            messages.append({"role": "assistant", "content": msg.content, "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]})

            # Execute each requested tool and append results
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                tool_args = json.loads(tc.function.arguments)

                if DEBUG:
                    print(f"  [DBG] executing {tool_name}({tool_args})", flush=True)

                try:
                    result = execute_tool(tool_name, tool_args, chat_id)
                except Exception as e:
                    result = {"error": str(e)}
                    print(f"  [DBG] execute_tool ERROR: {e}", flush=True)

                if DEBUG:
                    print(f"  [DBG] tool result: {json.dumps(result)[:120]}", flush=True)

                # Persist active_sale_id to DB if draft_sale just ran
                if tool_name == "tool_draft_sale" and "sale_id" in result:
                    set_preference(active_sale_key, result["sale_id"])
                elif tool_name == "tool_finalize_sale":
                    set_preference(active_sale_key, None)  # Clear after finalization

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })

            # Loop: give the LLM the tool results and let it continue
            continue

        # ── Case 2: LLM produced a plain text reply ───────────
        reply = msg.content or "(no response)"
        
        # Safety check: Catch hallucinated plain-text tool calls
        if "tool_" in reply and ("{" in reply or "(" in reply):
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user", "content": "ERROR: You returned raw text that looks like a tool call. You MUST use the native tool calling feature to execute tools, not plain text."})
            continue

        # Append assistant reply and user message to history for next turn
        updated_history = history + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": reply},
        ]

        return reply, updated_history

    # Safety fallback if MAX_TOOL_ROUNDS exceeded
    return "I ran into an issue processing that request. Please try again.", history
