import enum
import re
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urlsplit

import sqlalchemy as sa
from flask_login import UserMixin
from sqlalchemy.orm import Mapped, mapped_column, relationship

from stockroom.extensions import db


def utcnow() -> datetime:
    return datetime.now(UTC)


SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*:(?!\d)", re.IGNORECASE)


def normalize_url(value: str | None) -> str | None:
    """Return an http(s) URL, adding https:// when no scheme was given. Rejects other schemes."""
    value = (value or "").strip()
    if not value:
        return None
    # "host:8080/x" has no scheme; "mailto:x" or "javascript:x" do and must be rejected.
    if not SCHEME_RE.match(value):
        value = "https://" + value.removeprefix("//")
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError(f"Not a valid web address: {value}")
    return value


# Enum values are the human-readable labels; the database stores the member names.
class Role(enum.Enum):
    ADMIN = "Admin"
    PM = "Project manager"


class Status(enum.Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    ORDERED = "Ordered"
    SHIPPED = "Shipped"
    DELIVERED = "Delivered"
    CANCELED = "Canceled"


IN_PROGRESS = (Status.APPROVED, Status.ORDERED, Status.SHIPPED)


class Urgency(enum.Enum):
    END_OF_WEEK = "End of week"
    IMMEDIATE = "Immediate"


class ShippingSpeed(enum.Enum):
    GROUND = "Standard ground"
    THREE_DAY = "3-day"
    TWO_DAY = "2-day"
    OVERNIGHT = "Overnight"


class Courier(enum.Enum):
    USPS = "USPS"
    FEDEX = "FedEx"
    UPS = "UPS"
    DHL = "DHL"
    AMAZON = "Amazon"
    OTHER = "Other"


def enum_column(enum_cls):
    return sa.Enum(enum_cls, native_enum=False, length=20, validate_strings=True)


Money = sa.Numeric(10, 2)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(sa.String(255), unique=True)
    name: Mapped[str] = mapped_column(sa.String(255))
    role: Mapped[Role] = mapped_column(enum_column(Role))
    is_superuser: Mapped[bool] = mapped_column(default=False)
    project_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    project: Mapped["Project | None"] = relationship(back_populates="members")

    @property
    def is_admin(self) -> bool:
        return self.role is Role.ADMIN

    def can_access(self, project: "Project") -> bool:
        return self.is_admin or self.project_id == project.id


class Project(db.Model):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(255))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    members: Mapped[list[User]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by=User.name
    )
    orders: Mapped[list["Order"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Order.created_at.desc()"
    )

    @property
    def total(self) -> Decimal:
        return sum((o.total for o in self.orders if o.status is not Status.CANCELED), Decimal("0"))

    def count(self, *statuses: Status) -> int:
        return sum(o.status in statuses for o in self.orders)


class Order(db.Model):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        sa.ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    created_by_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    vendor: Mapped[str] = mapped_column(sa.String(255))
    vendor_url: Mapped[str | None] = mapped_column(sa.String(2048))
    urgency: Mapped[Urgency] = mapped_column(enum_column(Urgency))
    shipping_speed: Mapped[ShippingSpeed] = mapped_column(enum_column(ShippingSpeed))
    status: Mapped[Status] = mapped_column(enum_column(Status), default=Status.PENDING)
    courier: Mapped[Courier | None] = mapped_column(enum_column(Courier))
    tracking_url: Mapped[str | None] = mapped_column(sa.String(2048))
    shipping_cost: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))

    project: Mapped[Project] = relationship(back_populates="orders")
    created_by: Mapped[User | None] = relationship()
    items: Mapped[list["Item"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="Item.id"
    )

    @property
    def subtotal(self) -> Decimal:
        return sum((i.total for i in self.items), Decimal("0"))

    @property
    def total(self) -> Decimal:
        return self.subtotal + (self.shipping_cost or Decimal("0"))

    def can_delete(self, user: User) -> bool:
        if user.is_admin:
            return True
        return user.project_id == self.project_id and self.status is Status.PENDING


class Item(db.Model):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        sa.ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    description: Mapped[str] = mapped_column(sa.String(500))
    part_number: Mapped[str] = mapped_column(sa.String(255))
    unit_price: Mapped[Decimal] = mapped_column(Money)
    quantity: Mapped[int]
    justification: Mapped[str] = mapped_column(sa.Text)

    order: Mapped[Order] = relationship(back_populates="items")

    @property
    def total(self) -> Decimal:
        return self.unit_price * self.quantity
