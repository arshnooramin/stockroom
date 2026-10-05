import io
import re

import xlsxwriter

from stockroom.models import Project

HEADERS = [
    ("Order #", 9),
    ("Created (UTC)", 18),
    ("Vendor", 18),
    ("Vendor URL", 30),
    ("Status", 11),
    ("Urgency", 12),
    ("Shipping speed", 15),
    ("Courier", 10),
    ("Tracking URL", 30),
    ("Description", 30),
    ("Part number", 18),
    ("Unit price", 11),
    ("Quantity", 9),
    ("Line total", 11),
    ("Justification", 40),
    ("Order subtotal", 14),
    ("Shipping cost", 13),
    ("Order total", 12),
]


def _sheet_name(name: str, used: set[str]) -> str:
    # Excel sheet names: max 31 chars, no []:*?/\ and unique (case-insensitive).
    base = re.sub(r"[\[\]:*?/\\]", "-", name).strip() or "Project"
    candidate, n = base[:31], 2
    while candidate.lower() in used:
        suffix = f" ({n})"
        candidate, n = base[: 31 - len(suffix)] + suffix, n + 1
    used.add(candidate.lower())
    return candidate


def build_workbook(projects: list[Project]) -> io.BytesIO:
    """One sheet per project, one row per item, with order-level columns repeated for filtering."""
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "remove_timezone": True})
    bold = wb.add_format({"bold": True})
    money = wb.add_format({"num_format": "$#,##0.00"})
    when = wb.add_format({"num_format": "yyyy-mm-dd hh:mm"})
    used: set[str] = set()

    for project in projects:
        ws = wb.add_worksheet(_sheet_name(project.name, used))
        for col, (header, width) in enumerate(HEADERS):
            ws.write(0, col, header, bold)
            ws.set_column(col, col, width)
        ws.freeze_panes(1, 0)

        row = 1
        for order in project.orders:
            for item in order.items or [None]:
                values = [
                    (order.id, None),
                    (order.created_at, when),
                    (order.vendor, None),
                    (order.vendor_url or "", None),
                    (order.status.value, None),
                    (order.urgency.value, None),
                    (order.shipping_speed.value, None),
                    (order.courier.value if order.courier else "", None),
                    (order.tracking_url or "", None),
                    (item.description if item else "", None),
                    (item.part_number if item else "", None),
                    (float(item.unit_price) if item else "", money),
                    (item.quantity if item else "", None),
                    (float(item.total) if item else "", money),
                    (item.justification if item else "", None),
                    (float(order.subtotal), money),
                    (float(order.shipping_cost), money),
                    (float(order.total), money),
                ]
                for col, (value, fmt) in enumerate(values):
                    # write_string avoids Excel interpreting user text as formulas or URLs.
                    if isinstance(value, str):
                        ws.write_string(row, col, value)
                    else:
                        ws.write(row, col, value, fmt)
                row += 1
        if row > 1:
            ws.autofilter(0, 0, row - 1, len(HEADERS) - 1)

    wb.close()
    buf.seek(0)
    return buf
