"""
main.py — Nebula Supermarket Ops Agent
=======================================
Stage 9: FastAPI Server

Architecture rule (from master context):
  FastAPI route handlers MUST stay thin.
  Business logic lives in services/, not here.

Routes:
  GET  /health           — liveness check
  GET  /stock/{id}       — check stock for a product
  GET  /forecast/{id}    — demand forecast for a product
  GET  /khata/{cid}      — get customer khata balance
  GET  /analytics/today  — today's sales summary
  POST /invoice/{sid}    — generate PDF invoice, return file
  POST /webhook          — Telegram webhook (placeholder for Stage 14)
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os

from services.inventory   import check_stock
from services.forecasting import predict_demand
from services.khata        import get_khata_balance
from services.analytics    import get_daily_sales
from services.documents    import generate_invoice

from datetime import date


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    print("Nebula Supermarket Agent is starting up...")
    yield
    print("Nebula Supermarket Agent is shutting down.")


app = FastAPI(
    title="Nebula Supermarket Ops Agent",
    description="Backend API for the Nebula Supermarket conversational agent.",
    version="0.9.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health():
    """Liveness check. Returns OK if the server is running."""
    return {"status": "ok", "service": "nebula-supermarket-agent"}


# ─────────────────────────────────────────────────────────────
# INVENTORY
# ─────────────────────────────────────────────────────────────
@app.get("/stock/{product_id}", tags=["Inventory"])
def get_stock(product_id: str):
    """Returns current stock quantity for a product."""
    try:
        quantity = check_stock(product_id)
        return {"product_id": product_id, "quantity": quantity}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─────────────────────────────────────────────────────────────
# FORECASTING
# ─────────────────────────────────────────────────────────────
@app.get("/forecast/{product_id}", tags=["Forecasting"])
def forecast(product_id: str, days_ahead: int = 7, history_days: int = 30):
    """Returns demand forecast for a product using historical moving average."""
    try:
        return predict_demand(product_id, historical_days=history_days, forecast_days=days_ahead)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# KHATA
# ─────────────────────────────────────────────────────────────
@app.get("/khata/{customer_id}", tags=["Khata"])
def khata_balance(customer_id: str):
    """Returns the current khata (credit) balance for a customer."""
    try:
        balance = get_khata_balance(customer_id)
        return {"customer_id": customer_id, "balance": balance}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─────────────────────────────────────────────────────────────
# ANALYTICS
# ─────────────────────────────────────────────────────────────
@app.get("/analytics/today", tags=["Analytics"])
def analytics_today():
    """Returns today's sales analytics summary."""
    try:
        return get_daily_sales(date.today())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# DOCUMENT GENERATION
# ─────────────────────────────────────────────────────────────
@app.post("/invoice/{sale_id}", tags=["Documents"])
def invoice(sale_id: str):
    """
    Generates a PDF GST invoice for a finalized sale.
    Returns the PDF file directly as a download.
    """
    try:
        pdf_path = generate_invoice(sale_id)
        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=os.path.basename(pdf_path),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# TELEGRAM WEBHOOK (placeholder — wired in Stage 14)
# ─────────────────────────────────────────────────────────────
@app.post("/webhook", tags=["Telegram"])
async def telegram_webhook(payload: dict):
    """
    Telegram webhook endpoint.
    Stage 14 will wire this to the Agent.
    For now, it acknowledges receipt and logs the update.
    """
    print(f"[webhook] Received update: {payload.get('update_id', 'unknown')}")
    return {"status": "received"}


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
