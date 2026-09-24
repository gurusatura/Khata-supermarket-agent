"""
agent/tools.py — Nebula Supermarket Ops Agent
==============================================
Stage 11: Tool Definitions for the LLM Agent

These are the JSON Schema definitions that tell the LLM *what tools exist*
and *how to call them*. The LLM never sees our Python code — only these
instruction manuals.

The actual Python execution happens in agent/harness.py, which maps
each tool name to the correct services/ function.
"""

# ─────────────────────────────────────────────────────────────
# TOOL SCHEMAS (what the LLM sees)
# ─────────────────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "tool_check_stock",
            "description": (
                "Check how many units of a product are currently in stock. "
                "Use this when the user asks 'how much X is left?' or "
                "'do we have enough Y?'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "The name of the product to check stock for (e.g., 'Toor Dal', 'Maggi').",
                    }
                },
                "required": ["product_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_receive_stock",
            "description": (
                "Record incoming stock from a supplier. "
                "Use this when the user says 'we received X kg of Y' or 'new stock arrived'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "The name of the product received.",
                    },
                    "quantity": {
                        "type": "number",
                        "description": "How many units were received (kg, packets, etc.).",
                    },
                    "cost_price": {
                        "type": "number",
                        "description": "Cost price per unit paid to the supplier (in INR).",
                    },
                    "sell_price": {
                        "type": "number",
                        "description": "Selling price per unit to the customer (in INR).",
                    },
                },
                "required": ["product_name", "quantity", "cost_price", "sell_price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_draft_sale",
            "description": (
                "Start a new sale / open a new bill. "
                "Call this first before adding any items. "
                "Returns a sale_id that MUST be passed to subsequent tool calls. "
                "Use 'Walk-in Customer' if the customer name is not provided."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Customer name or 'Walk-in Customer'.",
                    },
                    "payment_mode": {
                        "type": "string",
                        "enum": ["CASH", "UPI", "KHATA"],
                        "description": "How the customer will pay.",
                    },
                },
                "required": ["customer_name", "payment_mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_add_item",
            "description": (
                "Add a product to an open draft bill. "
                "Requires a sale_id from tool_draft_sale. "
                "Call this for each item the customer wants to buy."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sale_id": {
                        "type": "string",
                        "description": "The sale UUID returned by tool_draft_sale.",
                    },
                    "product_name": {
                        "type": "string",
                        "description": "The name of the product to add.",
                    },
                    "quantity": {
                        "type": "number",
                        "description": "Quantity to add (in the product's unit — kg, packet, etc.).",
                    },
                },
                "required": ["sale_id", "product_name", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_remove_item",
            "description": (
                "Remove a product from an open draft bill. "
                "Use this when the customer changes their mind and says "
                "'remove X' or 'cancel the Y from my bill'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sale_id": {
                        "type": "string",
                        "description": "The sale UUID returned by tool_draft_sale.",
                    },
                    "product_name": {
                        "type": "string",
                        "description": "The name of the product to remove from the bill.",
                    },
                },
                "required": ["sale_id", "product_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_finalize_sale",
            "description": (
                "Finalize and close a draft bill. This deducts stock, "
                "calculates GST, and records the payment. "
                "Call this when the customer says 'done', 'finish bill', or 'that's all'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sale_id": {
                        "type": "string",
                        "description": "The sale UUID returned by tool_draft_sale.",
                    },
                },
                "required": ["sale_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_check_khata",
            "description": (
                "Check how much a customer owes on credit (khata). "
                "Use when the user asks 'what is X's balance?' or 'how much does Y owe?'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "The customer's name.",
                    }
                },
                "required": ["customer_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_record_khata_payment",
            "description": (
                "Record a khata (credit) repayment from a customer. "
                "Use when customer says 'X paid Y rupees' or 'record payment from Z'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "The customer's name.",
                    },
                    "amount": {
                        "type": "number",
                        "description": "Amount paid in INR.",
                    },
                },
                "required": ["customer_name", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_get_daily_analytics",
            "description": (
                "Get today's sales summary: total revenue, number of bills, "
                "breakdown by payment mode, and GST collected. "
                "Use when user asks 'how did we do today?' or 'today's total?'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format. Use today's date if not specified.",
                    }
                },
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_generate_invoice",
            "description": (
                "Generate a PDF GST invoice for a finalized sale and return the file path. "
                "Use when user asks 'send invoice' or 'give bill as PDF'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sale_id": {
                        "type": "string",
                        "description": "The finalized sale UUID.",
                    }
                },
                "required": ["sale_id"],
            },
        },
    },
]
