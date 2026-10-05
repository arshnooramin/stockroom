from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.datastructures import MultiDict

from stockroom.auth import admin_required
from stockroom.extensions import db
from stockroom.models import (
    Courier,
    Item,
    Order,
    Project,
    ShippingSpeed,
    Status,
    Urgency,
    normalize_url,
)
from stockroom.notifications import notify_new_order, notify_status_change
from stockroom.projects import get_project_or_404

bp = Blueprint("orders", __name__)

OTHER_VENDOR = "Other"
VENDORS = {
    "Digi-Key": "https://www.digikey.com",
    "Mouser": "https://www.mouser.com",
    "McMaster-Carr": "https://www.mcmaster.com",
    "Amazon": "https://www.amazon.com",
    "SparkFun": "https://www.sparkfun.com",
    "Pololu": "https://www.pololu.com",
    "Adafruit": "https://www.adafruit.com",
    "PCBWay": "https://www.pcbway.com",
    "OSH Park": "https://oshpark.com",
    "Advanced Circuits": "https://www.4pcb.com",
    "OSH Stencils": "https://www.oshstencils.com",
}
ITEM_FIELDS = ("description", "part_number", "unit_price", "quantity", "justification")


def parse_choice[E](enum_cls: type[E], value: str | None) -> E:
    try:
        return enum_cls[value or ""]
    except KeyError:
        raise ValueError(f"Invalid {enum_cls.__name__.lower()}: {value!r}") from None


def parse_money(value: str | None, label: str) -> Decimal:
    try:
        amount = Decimal((value or "").strip() or "0").quantize(Decimal("0.01"))
    except InvalidOperation:
        raise ValueError(f"{label} must be a number.") from None
    if not amount.is_finite() or not 0 <= amount < 10**8:
        raise ValueError(f"{label} must be between $0 and $99,999,999.99.")
    return amount


def submitted_items(form: MultiDict) -> list[dict[str, str]]:
    """Item rows exactly as submitted, so a rejected form re-renders with the user's input."""
    columns = [form.getlist(f"item_{f}") for f in ITEM_FIELDS]
    rows = [dict(zip(ITEM_FIELDS, values, strict=False)) for values in zip(*columns, strict=False)]
    return rows or [{}]


def parse_items(form: MultiDict) -> list[Item]:
    columns = [form.getlist(f"item_{f}") for f in ITEM_FIELDS]
    if len({len(c) for c in columns}) != 1 or not columns[0]:
        raise ValueError("Add at least one item.")

    items = []
    for n, (description, part_number, price, quantity, justification) in enumerate(
        zip(*columns, strict=True), start=1
    ):
        description, part_number, justification = (
            description.strip(),
            part_number.strip(),
            justification.strip(),
        )
        if not (description and part_number and justification):
            raise ValueError(f"Item {n}: description, part number and justification are required.")
        try:
            qty = int(quantity)
        except ValueError:
            raise ValueError(f"Item {n}: quantity must be a whole number.") from None
        if qty < 1:
            raise ValueError(f"Item {n}: quantity must be at least 1.")
        items.append(
            Item(
                description=description,
                part_number=part_number,
                unit_price=parse_money(price, f"Item {n} price"),
                quantity=qty,
                justification=justification,
            )
        )
    return items


def build_order(project: Project, form: MultiDict) -> Order:
    vendor = form.get("vendor", "")
    if vendor == OTHER_VENDOR:
        vendor = form.get("vendor_other_name", "").strip()
        if not vendor:
            raise ValueError("Enter the vendor's name.")
        vendor_url = normalize_url(form.get("vendor_other_url"))
    elif vendor in VENDORS:
        vendor_url = VENDORS[vendor]
    else:
        raise ValueError("Choose a vendor.")

    return Order(
        project=project,
        created_by=current_user,
        vendor=vendor,
        vendor_url=vendor_url,
        urgency=parse_choice(Urgency, form.get("urgency")),
        shipping_speed=parse_choice(ShippingSpeed, form.get("shipping_speed")),
        items=parse_items(form),
    )


@bp.route("/projects/<int:project_id>/orders/new", methods=["GET", "POST"])
@login_required
def new(project_id: int):
    project = get_project_or_404(project_id)
    if request.method == "POST":
        try:
            order = build_order(project, request.form)
        except ValueError as err:
            flash(str(err), "danger")
        else:
            db.session.add(order)
            db.session.commit()
            notify_new_order(order)
            flash(f"Order #{order.id} submitted.", "success")
            return redirect(url_for("projects.show", project_id=project.id))

    return render_template(
        "orders/new.html",
        project=project,
        vendors=VENDORS,
        other_vendor=OTHER_VENDOR,
        form=request.form,
        items=submitted_items(request.form),
    )


@bp.route("/orders/<int:order_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(order_id: int):
    order = db.get_or_404(Order, order_id)
    if request.method == "POST":
        form = request.form
        try:
            changes = {
                "status": parse_choice(Status, form.get("status")),
                "urgency": parse_choice(Urgency, form.get("urgency")),
                "shipping_speed": parse_choice(ShippingSpeed, form.get("shipping_speed")),
                "courier": parse_choice(Courier, form["courier"]) if form.get("courier") else None,
                "tracking_url": normalize_url(form.get("tracking_url")),
                "shipping_cost": parse_money(form.get("shipping_cost"), "Shipping cost"),
            }
        except ValueError as err:
            flash(str(err), "danger")
        else:
            status_changed = changes["status"] is not order.status
            for field, value in changes.items():
                setattr(order, field, value)
            db.session.commit()
            if status_changed:
                notify_status_change(order)
            flash(f"Order #{order.id} updated.", "success")
            return redirect(url_for("projects.show", project_id=order.project_id))

    return render_template("orders/edit.html", order=order)


@bp.post("/orders/<int:order_id>/delete")
@login_required
def delete(order_id: int):
    order = db.get_or_404(Order, order_id)
    if not current_user.can_access(order.project):
        abort(403)
    project_id = order.project_id
    if order.can_delete(current_user):
        db.session.delete(order)
        db.session.commit()
        flash(f"Order #{order_id} deleted.", "success")
    else:
        flash(
            "Only pending orders can be deleted. Ask an administrator to cancel it instead.",
            "danger",
        )
    return redirect(url_for("projects.show", project_id=project_id))
