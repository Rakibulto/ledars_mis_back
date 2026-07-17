from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile
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
            "reportlab is required only for work order PDF exports. "
            "Install backend requirements before using export features."
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


def _safe_decimal(value):
    try:
        return Decimal(str(value or 0))
    except (TypeError, ValueError, InvalidOperation):
        return Decimal("0.00")


def _format_currency(value):
    amount = _safe_decimal(value)
    return f"BDT {amount:,.2f}"


def _slugify(value):
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", _safe_text(value, "work-order"))
    return slug.strip("_") or "work-order"


def build_work_order_export_filename(data, extension):
    stem = _slugify(data.get("workOrderNumber") or data.get("id") or "work-order")
    return f"{stem}.{extension}"


def _split_terms(terms):
    if isinstance(terms, list):
        values = []
        for term in terms:
            values.extend([line.strip() for line in str(term or "").splitlines() if line.strip()])
        return values or ["No terms recorded."]
    if terms:
        values = [line.strip() for line in str(terms).splitlines() if line.strip()]
        return values or [str(terms).strip()]
    return ["No terms recorded."]


def _paragraph(text, style):
    Paragraph = _load_reportlab()["Paragraph"]
    return Paragraph(escape(_safe_text(text)), style)


def build_work_order_pdf_bytes(data):
    reportlab = _load_reportlab()
    colors = reportlab["colors"]
    A4 = reportlab["A4"]
    ParagraphStyle = reportlab["ParagraphStyle"]
    getSampleStyleSheet = reportlab["getSampleStyleSheet"]
    mm = reportlab["mm"]
    Paragraph = reportlab["Paragraph"]
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
        title=_safe_text(data.get("workOrderNumber") or data.get("id")),
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "WorkOrderTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "WorkOrderSubtitle",
        parent=styles["Heading2"],
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceAfter=8,
    )
    section_style = ParagraphStyle(
        "WorkOrderSection",
        parent=styles["Heading3"],
        fontSize=11,
        leading=13,
        spaceBefore=8,
        spaceAfter=6,
        textColor=colors.HexColor("#0f172a"),
    )
    body_style = ParagraphStyle(
        "WorkOrderBody",
        parent=styles["BodyText"],
        fontSize=9,
        leading=11,
    )
    small_style = ParagraphStyle(
        "WorkOrderSmall",
        parent=body_style,
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#475569"),
    )

    organization = data.get("organization") or {}
    vendor = data.get("vendor") or {}
    items = data.get("items") or []
    approval_chain = data.get("approvalChain") or []
    notification_log = data.get("notificationLog") or []

    story = [
        _paragraph(organization.get("name") or "Ledars NGO", title_style),
        _paragraph("Work Order / Purchase Order", subtitle_style),
        _paragraph(data.get("title") or "Work order export", body_style),
        Spacer(1, 4 * mm),
    ]

    organization_lines = [
        organization.get("address"),
        organization.get("email"),
        organization.get("phone"),
    ]
    if any(organization_lines):
        story.append(
            _paragraph(
                " | ".join([line for line in organization_lines if line]),
                small_style,
            )
        )
        story.append(Spacer(1, 4 * mm))

    metadata_rows = [
        ["WO Number", _safe_text(data.get("workOrderNumber") or data.get("id")), "Order Date", _safe_text(data.get("orderDate"))],
        ["Award", _safe_text(data.get("awardNumber")), "Delivery Deadline", _safe_text(data.get("deliveryDeadline"))],
        ["CS Ref", _safe_text(data.get("csNumber")), "RFQ Ref", _safe_text(data.get("rfqNumber"))],
        ["MRF Ref", _safe_text(data.get("requisitionNumber")), "Category", _safe_text(data.get("category"))],
        ["Budget Code", _safe_text(data.get("budgetCode")), "Project", _safe_text(data.get("project"))],
        ["Status", _safe_text(data.get("status")), "Vendor Status", _safe_text(data.get("vendorStatus"))],
    ]

    metadata_table = Table(metadata_rows, colWidths=[26 * mm, 54 * mm, 30 * mm, 60 * mm])
    metadata_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("LEADING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([metadata_table, Spacer(1, 5 * mm)])

    story.append(_paragraph("Vendor Information", section_style))
    vendor_table = Table(
        [
            ["Vendor", _safe_text(vendor.get("name")), "Contact", _safe_text(vendor.get("contactPerson"))],
            ["Email", _safe_text(vendor.get("email")), "Phone", _safe_text(vendor.get("phone"))],
            ["Address", _safe_text(vendor.get("address")), "Delivery", _safe_text(data.get("deliveryLocation"))],
            ["Payment Terms", _safe_text(data.get("paymentTerms")), "Warranty", _safe_text(data.get("warrantyPeriod"))],
        ],
        colWidths=[24 * mm, 56 * mm, 24 * mm, 66 * mm],
    )
    vendor_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([vendor_table, Spacer(1, 5 * mm)])

    story.append(_paragraph("Order Items", section_style))
    item_rows = [["SL", "Description & Specifications", "Qty", "Unit Price", "Total"]]
    for index, item in enumerate(items, start=1):
        description = f"<b>{escape(_safe_text(item.get('description') or item.get('name')))}</b><br/>{escape(_safe_text(item.get('specification')))}"
        item_rows.append(
            [
                str(index),
                Paragraph(description, body_style),
                _safe_text(item.get("quantity"), "0"),
                _format_currency(item.get("unitPrice")),
                _format_currency(item.get("total")),
            ]
        )
    item_rows.append(["", "Grand Total", "", "", _format_currency(data.get("totalAmount"))])
    item_table = Table(item_rows, colWidths=[10 * mm, 88 * mm, 18 * mm, 34 * mm, 32 * mm])
    item_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#94a3b8")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([item_table, Spacer(1, 5 * mm)])

    story.append(_paragraph("Terms & Conditions", section_style))
    for index, term in enumerate(_split_terms(data.get("termsAndConditions")), start=1):
        story.append(_paragraph(f"{index}. {term}", body_style))
        story.append(Spacer(1, 1.2 * mm))

    if data.get("notes"):
        story.extend(
            [
                Spacer(1, 2 * mm),
                _paragraph("Special Instructions", section_style),
                _paragraph(data.get("notes"), body_style),
            ]
        )

    if approval_chain:
        story.extend([Spacer(1, 3 * mm), _paragraph("Approval History", section_style)])
        approval_rows = [["Approver", "Role", "Action", "Date", "Comments"]]
        for approval in approval_chain:
            approval_rows.append(
                [
                    _safe_text(approval.get("approver")),
                    _safe_text(approval.get("role")),
                    _safe_text(approval.get("action")),
                    _safe_text(approval.get("date")),
                    Paragraph(escape(_safe_text(approval.get("comments"))), small_style),
                ]
            )
        approval_table = Table(
            approval_rows,
            colWidths=[33 * mm, 30 * mm, 22 * mm, 28 * mm, 52 * mm],
        )
        approval_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.extend([approval_table, Spacer(1, 4 * mm)])

    if notification_log:
        story.append(_paragraph("Notification Log", section_style))
        notification_rows = [["Channel", "Status", "Recipient", "Date"]]
        for entry in notification_log:
            notification_rows.append(
                [
                    _safe_text(entry.get("channel")),
                    _safe_text(entry.get("status")),
                    _safe_text(entry.get("recipient")),
                    _safe_text(entry.get("date") or entry.get("sentAt")),
                ]
            )
        notification_table = Table(notification_rows, colWidths=[30 * mm, 24 * mm, 74 * mm, 32 * mm])
        notification_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(notification_table)

    document.build(story)
    return buffer.getvalue()


def build_work_order_document_bundle_bytes(work_order, data):
    buffer = BytesIO()
    pdf_name = build_work_order_export_filename(data, "pdf")
    pdf_bytes = build_work_order_pdf_bytes(data)
    generated_files = []

    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(pdf_name, pdf_bytes)
        generated_files.append(pdf_name)

        for attachment in work_order.attachments.all():
            if not attachment.file:
                continue
            file_name = _slugify(attachment.name or Path(attachment.file.name).name)
            archive_name = f"attachments/{file_name}"
            attachment.file.open("rb")
            try:
                archive.writestr(archive_name, attachment.file.read())
            finally:
                attachment.file.close()
            generated_files.append(archive_name)

        vendor_acceptance = getattr(work_order, "vendor_acceptance", None)
        if vendor_acceptance and vendor_acceptance.attachment:
            file_name = _slugify(Path(vendor_acceptance.attachment.name).name)
            archive_name = f"vendor-acceptance/{file_name}"
            vendor_acceptance.attachment.open("rb")
            try:
                archive.writestr(archive_name, vendor_acceptance.attachment.read())
            finally:
                vendor_acceptance.attachment.close()
            generated_files.append(archive_name)

        archive.writestr(
            "README.txt",
            "\n".join(
                [
                    f"Work Order: {_safe_text(data.get('workOrderNumber') or data.get('id'))}",
                    f"Title: {_safe_text(data.get('title'))}",
                    f"Vendor: {_safe_text((data.get('vendor') or {}).get('name'))}",
                    f"Total Amount: {_format_currency(data.get('totalAmount'))}",
                    "",
                    "Included files:",
                    *generated_files,
                ]
            ),
        )

    return buffer.getvalue()