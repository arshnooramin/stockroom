import zlib
from datetime import datetime
from decimal import Decimal


def money(value: Decimal | float | None) -> str:
    return f"${value or 0:,.2f}"


def date(value: datetime | None) -> str:
    return f"{value:%b} {value.day}, {value.year}" if value else ""


def initials(name: str) -> str:
    parts = name.split()
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper() if parts else "?"


def avatar_hue(name: str) -> int:
    """A stable hue per name so the same person always gets the same avatar color."""
    return zlib.crc32(name.encode()) % 360


def init_app(app):
    for fn in (money, date, initials, avatar_hue):
        app.add_template_filter(fn)
