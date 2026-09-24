# Nebula Supermarket Ops Agent 🤖🛒

An autonomous, agentic workflow system designed to handle multi-turn supermarket operations securely via Telegram. This agent doesn't just chat—it manages active shopping carts, processes inventory, finalizes sales, calculates **GST taxes**, handles complex Khata (credit) accounts, and guarantees strict database grounding.

**Telegram Bot:** (Set up and running live on Telegram)

## 🌟 Key Engineering Highlights & Problem Solving

This project was built with a heavy focus on **data integrity, concurrency, and hallucination prevention**. When delegating database operations to an LLM, safety is the top priority.

### 1. Robust Agent Control Loop
- **Custom ReAct Harness:** Instead of relying on rigid third-party frameworks, the agent runs on a custom Python control loop (`harness.py`). It forces the LLM to think, select tools, parse arguments, and observe the database output before replying.

### 2. Strict Grounding & Anti-Hallucination Guardrails
- **Khata Protection:** Small models tend to perform "mental math" and hallucinate balances instead of triggering tools. We implemented a strict system prompt guardrail that outright bans the LLM from calculating payments in its head. The agent is forced to use the `tool_record_khata_payment` tool, ensuring the database is always the absolute source of truth.
- **Ambiguous Lookup Guard (Exact-then-Fuzzy):** Initially, the `ILIKE '%name%' LIMIT 1` lookup allowed the agent to silently apply bills to the wrong customer if names were similar (e.g., "Ramesh" vs "Ramesh Kumar"). We rewired the executor to enforce an **Exact Match** first. If it falls back to a fuzzy match and finds *multiple* results, it throws an intentional `ValueError`, forcing the LLM to ask the user for clarification rather than corrupting data.

### 3. Concurrency & Idempotency
- **State Isolation:** The agent tracks active sales via `chat_id` (`active_sale_id:{chat_id}`). Multiple customers can interface with the Telegram bot simultaneously without their shopping carts bleeding into each other.
- **Idempotency Gates:** Finalizing a sale involves multiple database writes (inventory deduction, sales record creation, khata updates). To prevent double-charging if the LLM loops or retries a tool call, we gate sales behind an idempotency check (`request_id` and `sale_id`). The system explicitly refuses duplicate finalize requests.

### 4. Rich Document Generation (PDF & PPTX)
- **Automated Invoices (PDF):** The agent generates beautifully formatted PDF receipts featuring accurate **GST breakdowns** based on the specific products sold.
- **Analytics Presentations (PPTX):** The agent can query daily sales analytics and compile them into a multi-slide PowerPoint presentation automatically.

### 5. Resilient Telegram Integration
- **Long-Polling over Webhooks:** For maximum stability during the review process, the Telegram integration uses a robust long-polling script (`telegram_bot.py`) instead of relying on fragile, expiring free SSH tunnels (like Ngrok or Serveo). If the database or agent crashes, a top-level try/except wrapper intercepts the crash and sends a clean *"Sorry, something went wrong"* to the user, preventing raw stack traces from leaking into the Telegram UI.

## 🛠️ Tech Stack
- **AI/Agent:** Local Qwen model orchestrated via a custom Python harness (no heavy external frameworks like Langchain).
- **Backend:** FastAPI for PDF/Analytics endpoints, Python standard library for Telegram polling.
- **Database:** Supabase (PostgreSQL) with `psycopg`.

## ⚙️ How to Run the Project

### Prerequisites
1. Python 3.10+
2. A Supabase PostgreSQL database
3. A Telegram Bot Token

### Setup
1. Clone the repository.
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your `DATABASE_URL` and `TELEGRAM_BOT_TOKEN`.
4. Run the database setup script to initialize the schema: 
   ```bash
   python scripts/setup_db.py
   ```

### Running the Agent
Start the Telegram polling bot. This will keep the bot online and actively listening for messages:
```bash
python telegram_bot.py
```

### Running the API Server (Optional - for Webhooks/PDF generation)
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## ⚠️ Known Minor Issues
- **Live PDF Transmission via Telegram:** The `generate_invoice` tool successfully creates and saves PDF invoices locally (verified standalone). However, when triggered through the multi-turn Telegram flow, the LLM outputs the local file path instead of uploading the binary document over the Telegram API. The core PDF logic is fully functional (the PDF exists on disk), but the final transmission step via Telegram UI is a known quirk.

## 🧪 Scenarios Tested
- [x] Multi-item addition and cart editing.
- [x] Oversell guard (preventing the sale of out-of-stock items).
- [x] Concurrent chat isolation (Customer A and Customer B do not overlap).
- [x] Khata balance fetching and strictly-grounded payment recording.
- [x] Idempotent transaction finalizing.
- [x] PDF Invoice and PPTX Generation.
