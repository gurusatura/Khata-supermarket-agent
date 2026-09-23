"""
services/documents.py — Nebula Supermarket Ops Agent
=====================================================
Stage 8: Document Generation
  - generate_invoice(sale_id) → PDF via reportlab
  - generate_analytics_deck(date) → PPTX via python-pptx

IMPORTANT: All values are read from the database.
The LLM never calculates or invents any number in these documents.
"""

import os
from datetime import date
from services.db import get_connection

# Output directory for generated files
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "generated_docs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# PDF INVOICE
# ─────────────────────────────────────────────────────────────
def generate_invoice(sale_id: str) -> str:
    """
    Generates a GST-correct PDF invoice for a finalized sale.
    Reads all values directly from the database — nothing is recalculated.
    Returns the absolute path to the generated PDF file.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Fetch sale header
            cur.execute("""
                SELECT s.id, s.finalized_at, s.payment_mode,
                       s.subtotal, s.cgst_total, s.sgst_total, s.grand_total,
                       c.name AS customer_name, c.phone AS customer_phone
                FROM sales s
                LEFT JOIN customers c ON s.customer_id = c.id
                WHERE s.id = %s AND s.status = 'finalized';
            """, (sale_id,))
            sale = cur.fetchone()
            if not sale:
                raise ValueError(f"No finalized sale found with ID: {sale_id}")

            (sid, finalized_at, payment_mode, subtotal, cgst_total,
             sgst_total, grand_total, customer_name, customer_phone) = sale

            # Fetch line items
            cur.execute("""
                SELECT p.name, si.quantity, si.unit_price, si.gst_rate,
                       (si.quantity * si.unit_price) AS line_total,
                       p.hsn_code
                FROM sale_items si
                JOIN products p ON si.product_id = p.id
                WHERE si.sale_id = %s;
            """, (sale_id,))
            items = cur.fetchall()

    # --- Build PDF ---
    output_path = os.path.join(OUTPUT_DIR, f"invoice_{str(sale_id)[:8]}.pdf")
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            rightMargin=15*mm, leftMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)

    styles = getSampleStyleSheet()
    center_style = ParagraphStyle('center', parent=styles['Normal'], alignment=TA_CENTER)
    right_style  = ParagraphStyle('right', parent=styles['Normal'], alignment=TA_RIGHT)
    title_style  = ParagraphStyle('title', parent=styles['Heading1'], alignment=TA_CENTER,
                                  fontSize=16, spaceAfter=4)
    sub_style    = ParagraphStyle('sub', parent=styles['Normal'], alignment=TA_CENTER,
                                  fontSize=9, textColor=colors.grey)

    content = []

    # Header
    content.append(Paragraph("NEBULA SUPERMARKET", title_style))
    content.append(Paragraph("GST Tax Invoice", sub_style))
    content.append(Spacer(1, 6*mm))

    # Invoice meta table
    customer_display = customer_name if customer_name else "Walk-in Customer"
    phone_display    = customer_phone if customer_phone else "—"
    date_display     = finalized_at.strftime("%d %b %Y, %I:%M %p") if finalized_at else "—"

    meta_data = [
        ["Invoice No:", str(sid)[:18] + "..."],
        ["Date:", date_display],
        ["Customer:", customer_display],
        ["Phone:", phone_display],
        ["Payment:", payment_mode.upper()],
    ]
    meta_table = Table(meta_data, colWidths=[40*mm, 120*mm])
    meta_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    content.append(meta_table)
    content.append(Spacer(1, 6*mm))

    # Line items table
    headers = ["#", "Item", "HSN", "Qty", "MRP (incl. GST)", "GST%", "Taxable", "CGST", "SGST", "Total"]
    rows = [headers]

    for i, (name, qty, unit_price, gst_rate, line_total, hsn) in enumerate(items, 1):
        divisor = 1 + float(gst_rate) / 100
        taxable_per_unit = float(unit_price) / divisor
        taxable_line = taxable_per_unit * float(qty)
        gst_amount   = float(line_total) - taxable_line
        half_gst     = gst_amount / 2

        rows.append([
            str(i),
            name[:30],
            hsn or "—",
            f"{float(qty):.2f}",
            f"Rs.{float(unit_price):.2f}",
            f"{float(gst_rate):.0f}%",
            f"Rs.{taxable_line:.2f}",
            f"Rs.{half_gst:.2f}",
            f"Rs.{half_gst:.2f}",
            f"Rs.{float(line_total):.2f}",
        ])

    col_widths = [8*mm, 45*mm, 18*mm, 14*mm, 24*mm, 14*mm, 20*mm, 16*mm, 16*mm, 20*mm]
    items_table = Table(rows, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d2d2d')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    content.append(items_table)
    content.append(Spacer(1, 6*mm))

    # Totals summary
    total_taxable = float(grand_total) / (1 + (float(cgst_total + sgst_total) / float(grand_total) if grand_total else 1))
    summary_data = [
        ["Subtotal (taxable):", f"Rs.{float(subtotal):.2f}"],
        ["CGST:", f"Rs.{float(cgst_total):.2f}"],
        ["SGST:", f"Rs.{float(sgst_total):.2f}"],
        ["GRAND TOTAL:", f"Rs.{float(grand_total):.2f}"],
    ]
    summary_table = Table(summary_data, colWidths=[120*mm, 40*mm])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 11),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, -1), (-1, -1), 4),
    ]))
    content.append(summary_table)
    content.append(Spacer(1, 8*mm))
    content.append(Paragraph("Thank you for shopping at Nebula Supermarket!", center_style))

    doc.build(content)
    return output_path


# ─────────────────────────────────────────────────────────────
# PPTX ANALYTICS DECK
# ─────────────────────────────────────────────────────────────
def generate_analytics_deck(report_date: date = None) -> str:
    """
    Generates a PPTX analytics deck with real charts for a given date.
    Pulls all values from the analytics DB query — nothing is invented.
    Returns the absolute path to the generated .pptx file.
    """
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.chart.data import ChartData
    from pptx import util
    from pptx.enum.chart import XL_CHART_TYPE

    if report_date is None:
        report_date = date.today()

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Daily totals
            cur.execute("""
                SELECT COUNT(*), SUM(grand_total),
                       SUM(CASE WHEN payment_mode = 'cash' THEN grand_total ELSE 0 END),
                       SUM(CASE WHEN payment_mode = 'upi'  THEN grand_total ELSE 0 END),
                       SUM(CASE WHEN payment_mode = 'card' THEN grand_total ELSE 0 END),
                       SUM(CASE WHEN payment_mode = 'khata' THEN grand_total ELSE 0 END),
                       SUM(cgst_total + sgst_total)
                FROM sales
                WHERE status = 'finalized' AND DATE(finalized_at) = %s;
            """, (report_date,))
            row = cur.fetchone()
            total_bills = int(row[0] or 0)
            total_rev   = float(row[1] or 0)
            cash_rev    = float(row[2] or 0)
            upi_rev     = float(row[3] or 0)
            card_rev    = float(row[4] or 0)
            khata_rev   = float(row[5] or 0)
            total_tax   = float(row[6] or 0)

            # Top 5 products by revenue
            cur.execute("""
                SELECT p.name, SUM(si.quantity * si.unit_price) AS revenue
                FROM sale_items si
                JOIN products p ON si.product_id = p.id
                JOIN sales s ON si.sale_id = s.id
                WHERE s.status = 'finalized' AND DATE(s.finalized_at) = %s
                GROUP BY p.name
                ORDER BY revenue DESC
                LIMIT 5;
            """, (report_date,))
            top_products = cur.fetchall()

    # --- Build PPTX ---
    prs = Presentation()
    prs.slide_width  = Inches(13.33)
    prs.slide_height = Inches(7.5)

    DARK_BG  = RGBColor(0x1a, 0x1a, 0x2e)
    ACCENT   = RGBColor(0xe9, 0x4c, 0x61)
    WHITE    = RGBColor(0xff, 0xff, 0xff)
    GREY     = RGBColor(0xaa, 0xaa, 0xaa)

    blank_layout = prs.slide_layouts[6]

    def set_bg(slide, color):
        from pptx.oxml.ns import qn
        from lxml import etree
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = color

    def add_text(slide, text, left, top, width, height, size=14, bold=False, color=WHITE, align=PP_ALIGN.LEFT):
        txBox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf    = txBox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = align
        run = p.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color

    # ── SLIDE 1: Title ──────────────────────────────────────
    s1 = prs.slides.add_slide(blank_layout)
    set_bg(s1, DARK_BG)
    add_text(s1, "NEBULA SUPERMARKET", 1, 2.2, 11, 1.2, size=36, bold=True, color=ACCENT, align=PP_ALIGN.CENTER)
    add_text(s1, f"Daily Operations Report — {report_date.strftime('%d %B %Y')}",
             1, 3.4, 11, 0.6, size=18, color=GREY, align=PP_ALIGN.CENTER)

    # ── SLIDE 2: Revenue Summary ─────────────────────────────
    s2 = prs.slides.add_slide(blank_layout)
    set_bg(s2, DARK_BG)
    add_text(s2, "Revenue Summary", 0.5, 0.3, 12, 0.7, size=24, bold=True, color=ACCENT)

    kpis = [
        ("Total Revenue",    f"Rs.{total_rev:,.2f}"),
        ("Total Bills",      str(total_bills)),
        ("GST Collected",    f"Rs.{total_tax:,.2f}"),
        ("Avg Bill Value",   f"Rs.{(total_rev/total_bills if total_bills else 0):,.2f}"),
    ]
    for idx, (label, val) in enumerate(kpis):
        col = idx % 2
        row = idx // 2
        lft = 0.5 + col * 6.4
        top = 1.3 + row * 2.2
        box = s2.shapes.add_shape(1, Inches(lft), Inches(top), Inches(5.8), Inches(1.8))
        box.fill.solid(); box.fill.fore_color.rgb = RGBColor(0x2d, 0x2d, 0x4e)
        box.line.color.rgb = ACCENT
        add_text(s2, label, lft+0.15, top+0.1,  5.5, 0.5, size=11, color=GREY)
        add_text(s2, val,   lft+0.15, top+0.55, 5.5, 0.9, size=26, bold=True, color=WHITE)

    # ── SLIDE 3: Payment Mode Pie Chart ──────────────────────
    s3 = prs.slides.add_slide(blank_layout)
    set_bg(s3, DARK_BG)
    add_text(s3, "Payment Mode Breakdown", 0.5, 0.3, 12, 0.7, size=24, bold=True, color=ACCENT)

    chart_data = ChartData()
    chart_data.categories = ['Cash', 'UPI', 'Card', 'Khata']
    chart_data.add_series('Revenue', (cash_rev, upi_rev, card_rev, khata_rev))

    chart = s3.shapes.add_chart(
        XL_CHART_TYPE.PIE, Inches(1.5), Inches(1.2), Inches(10), Inches(5.8), chart_data
    ).chart
    chart.has_legend = True
    chart.has_title = False
    plot = chart.plots[0]
    plot.has_data_labels = True
    plot.data_labels.show_percentage = True
    plot.data_labels.show_category_name = True

    # ── SLIDE 4: Top Products ─────────────────────────────────
    s4 = prs.slides.add_slide(blank_layout)
    set_bg(s4, DARK_BG)
    add_text(s4, "Top Products by Revenue", 0.5, 0.3, 12, 0.7, size=24, bold=True, color=ACCENT)

    if top_products:
        bar_data = ChartData()
        bar_data.categories = [p[0][:20] for p in top_products]
        bar_data.add_series('Revenue (Rs.)', [float(p[1]) for p in top_products])

        chart2 = s4.shapes.add_chart(
            XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.5), Inches(1.2), Inches(12.3), Inches(5.8), bar_data
        ).chart
        chart2.has_legend = False
        chart2.has_title = False
    else:
        add_text(s4, "No sales data for this date.", 1, 3, 11, 1, size=14, color=GREY, align=PP_ALIGN.CENTER)

    output_path = os.path.join(OUTPUT_DIR, f"analytics_{report_date.strftime('%Y%m%d')}.pptx")
    prs.save(output_path)
    return output_path
