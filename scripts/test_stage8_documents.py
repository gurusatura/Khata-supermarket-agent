"""
test_stage8_documents.py — Nebula Supermarket Ops Agent
========================================================
Stage 8: Document Generation Test
Generates a real PDF invoice and a real PPTX analytics deck.
Open the files to visually verify them.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.db import get_connection
from services.documents import generate_invoice, generate_analytics_deck

def get_latest_finalized_sale():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM sales WHERE status = 'finalized'
                ORDER BY finalized_at DESC LIMIT 1;
            """)
            row = cur.fetchone()
            return str(row[0]) if row else None

def run():
    print("Stage 8: Document Generation Test")
    print("-" * 50)

    # --- TEST 1: PDF Invoice ---
    print("\n[1] Generating PDF Invoice...")
    sale_id = get_latest_finalized_sale()
    if not sale_id:
        print("    No finalized sales found. Run test_stage4.py first.")
        sys.exit(1)

    print(f"    Using Sale ID: {sale_id[:18]}...")
    pdf_path = generate_invoice(sale_id)
    print(f"    PDF saved to: {pdf_path}")

    assert os.path.exists(pdf_path), "PDF file was not created!"
    size_kb = os.path.getsize(pdf_path) / 1024
    print(f"    File size: {size_kb:.1f} KB")
    assert size_kb > 1, "PDF seems too small — might be empty!"
    print("    PDF Invoice: PASSED")

    # --- TEST 2: PPTX Analytics Deck ---
    print("\n[2] Generating PPTX Analytics Deck...")
    from datetime import date
    pptx_path = generate_analytics_deck(date.today())
    print(f"    PPTX saved to: {pptx_path}")

    assert os.path.exists(pptx_path), "PPTX file was not created!"
    size_kb = os.path.getsize(pptx_path) / 1024
    print(f"    File size: {size_kb:.1f} KB")
    assert size_kb > 1, "PPTX seems too small — might be empty!"
    print("    PPTX Analytics Deck: PASSED")

    print("\n" + "=" * 50)
    print("ALL STAGE 8 TESTS PASSED!")
    print("\nOpen these files to verify visually:")
    print(f"  PDF:  {pdf_path}")
    print(f"  PPTX: {pptx_path}")

if __name__ == "__main__":
    run()
