from io import BytesIO
from xml.sax.saxutils import escape

from django.core.exceptions import ImproperlyConfigured


def _load_reportlab():
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ModuleNotFoundError as exc:
        if exc.name != "reportlab":
            raise

        raise ImproperlyConfigured(
            "reportlab is required only for Project Management expense PDF exports. "
            "Install backend requirements before using invoice exports."
        ) from exc

    return {
        "colors": colors,
        "A4": A4,
        "ParagraphStyle": ParagraphStyle,
        "getSampleStyleSheet": getSampleStyleSheet,
        "mm": mm,
        "Paragraph": Paragraph,
        "SimpleDocTemplate": SimpleDocTemplate,
        "Spacer": Spacer,
        "Table": Table,
        "TableStyle": TableStyle,
    }


def _safe_text(value, fallback="-"):
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _paragraph(text, style):
    Paragraph = _load_reportlab()["Paragraph"]
    return Paragraph(escape(_safe_text(text)), style)


def _format_currency(amount, currency="BDT"):
    numeric_amount = float(amount or 0)
    return f"{currency} {numeric_amount:,.2f}"


def build_project_management_expense_pdf_bytes(expense):
    reportlab = _load_reportlab()
    colors = reportlab["colors"]
    A4 = reportlab["A4"]
    ParagraphStyle = reportlab["ParagraphStyle"]
    getSampleStyleSheet = reportlab["getSampleStyleSheet"]
    mm = reportlab["mm"]
    SimpleDocTemplate = reportlab["SimpleDocTemplate"]
    Spacer = reportlab["Spacer"]
    Table = reportlab["Table"]
    TableStyle = reportlab["TableStyle"]

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=_safe_text(expense.invoice_number or expense.title),
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ExpenseInvoiceTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "ExpenseInvoiceSubtitle",
        parent=styles["Heading2"],
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceAfter=10,
    )
    section_style = ParagraphStyle(
        "ExpenseInvoiceSection",
        parent=styles["Heading3"],
        fontSize=11,
        leading=13,
        spaceBefore=8,
        spaceAfter=6,
        textColor=colors.HexColor("#0f172a"),
    )
    body_style = ParagraphStyle(
        "ExpenseInvoiceBody",
        parent=styles["BodyText"],
        fontSize=9,
        leading=11,
    )
    small_style = ParagraphStyle(
        "ExpenseInvoiceSmall",
        parent=body_style,
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#475569"),
    )

    story = [
        _paragraph(expense.project.title if expense.project_id else "Project Expense", title_style),
        _paragraph("Expense Invoice", subtitle_style),
        _paragraph(expense.title, body_style),
        Spacer(1, 4 * mm),
    ]

    metadata_rows = [
        ["Invoice Number", _safe_text(expense.invoice_number), "Status", _safe_text(expense.status)],
        ["Expense Date", _safe_text(expense.expense_date), "Currency", _safe_text(expense.currency_code)],
        ["Project", _safe_text(expense.project.title if expense.project_id else "-"), "Task", _safe_text(expense.plan.title if expense.plan_id else "-")],
        ["Vendor / Payee", _safe_text(expense.vendor_name), "Prepared By", _safe_text(expense.created_by.username if expense.created_by_id else "-")],
    ]

    metadata_table = Table(metadata_rows, colWidths=[32 * mm, 58 * mm, 28 * mm, 56 * mm])
    metadata_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(metadata_table)

    if expense.description:
        story.extend(
            [
                Spacer(1, 5 * mm),
                _paragraph("Description", section_style),
                _paragraph(expense.description, body_style),
            ]
        )

    story.extend([Spacer(1, 5 * mm), _paragraph("Bill Lines", section_style)])

    item_rows = [["Description", "Analytic / Notes", "Qty", "Unit Price", "Amount"]]
    for item in expense.items.all():
        item_rows.append(
            [
                _safe_text(item.title),
                _safe_text(item.description),
                f"{float(item.quantity or 0):,.2f}",
                _format_currency(item.unit_price, expense.currency_code),
                _format_currency(item.line_total, expense.currency_code),
            ]
        )

    items_table = Table(item_rows, colWidths=[54 * mm, 42 * mm, 18 * mm, 30 * mm, 30 * mm])
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(items_table)

    totals_rows = [["Total", _format_currency(expense.total_amount, expense.currency_code)]]
    totals_table = Table(totals_rows, colWidths=[44 * mm, 36 * mm], hAlign="RIGHT")
    totals_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([Spacer(1, 5 * mm), totals_table])

    timeline_lines = [
        f"Created: {_safe_text(expense.created_at)}",
        f"Submitted: {_safe_text(expense.submitted_at)}",
        f"Approved: {_safe_text(expense.approved_at)}",
        f"Paid: {_safe_text(expense.paid_at)}",
    ]
    story.extend([Spacer(1, 5 * mm), _paragraph("Status Timeline", section_style)])
    for line in timeline_lines:
        story.append(_paragraph(line, small_style))

    document.build(story)
    buffer.seek(0)
    return buffer.getvalue()
