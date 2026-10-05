from decimal import Decimal

import pytest

from stockroom.extensions import db
from stockroom.models import Order, Status, normalize_url


def fresh(model, id_):
    db.session.expire_all()
    return db.session.get(model, id_)


def order_form(**overrides):
    form = {
        "vendor": "Mouser",
        "urgency": "END_OF_WEEK",
        "shipping_speed": "TWO_DAY",
        "item_description": ["Capacitor", "Header"],
        "item_part_number": ["C-1", "H-2"],
        "item_unit_price": ["1.25", "0.5"],
        "item_quantity": ["4", "3"],
        "item_justification": ["Decoupling", "Connectors"],
    }
    form.update(overrides)
    return form


def test_pm_creates_order(client, login, data, sent_emails):
    login(data["pm_a"])
    resp = client.post(f"/projects/{data['a']}/orders/new", data=order_form())
    assert resp.status_code == 302

    order = db.session.scalar(db.select(Order).filter_by(vendor="Mouser"))
    assert order.subtotal == Decimal("6.50")
    assert order.urgency.name == "END_OF_WEEK"
    assert order.vendor_url == "https://www.mouser.com"
    assert order.created_by.email == "pm.a@example.com"
    assert sent_emails == [(["admin@example.com"], f"New order #{order.id} from Project A")]


def test_other_vendor_url_normalized(client, login, data, sent_emails):
    login(data["pm_a"])
    client.post(
        f"/projects/{data['a']}/orders/new",
        data=order_form(vendor="Other", vendor_other_name="Acme", vendor_other_url="acme.example"),
    )
    order = db.session.scalar(db.select(Order).filter_by(vendor="Acme"))
    assert order.vendor_url == "https://acme.example"


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"item_quantity": ["0", "1"]}, b"quantity must be at least 1"),
        ({"item_unit_price": ["abc", "1"]}, b"must be a number"),
        ({"item_unit_price": ["NaN", "1"]}, b"must be between"),
        ({"item_description": ["", "x"]}, b"are required"),
        ({"vendor": "Nope"}, b"Choose a vendor"),
        (
            {
                "vendor": "Other",
                "vendor_other_name": "X",
                "vendor_other_url": "javascript:alert(1)",
            },
            b"Not a valid web address",
        ),
        ({"urgency": "SOON"}, b"Invalid urgency"),
    ],
)
def test_invalid_order_rejected_and_input_kept(client, login, data, overrides, message):
    login(data["pm_a"])
    resp = client.post(f"/projects/{data['a']}/orders/new", data=order_form(**overrides))
    assert resp.status_code == 200
    assert message in resp.data
    assert b"Decoupling" in resp.data  # submitted item rows are re-rendered
    assert db.session.scalar(db.select(db.func.count(Order.id))) == 1


def test_pm_cannot_see_or_order_for_other_project(client, login, data):
    login(data["pm_a"])
    assert client.get(f"/projects/{data['b']}").status_code == 403
    assert client.post(f"/projects/{data['b']}/orders/new", data=order_form()).status_code == 403


def test_pm_cannot_edit_orders(client, login, data):
    login(data["pm_a"])
    assert client.get(f"/orders/{data['order']}/edit").status_code == 403


def test_pm_deletes_pending_order(client, login, data):
    login(data["pm_a"])
    client.post(f"/orders/{data['order']}/delete")
    assert fresh(Order, data["order"]) is None


def test_pm_cannot_delete_approved_order(client, login, data):
    order = db.session.get(Order, data["order"])
    order.status = Status.APPROVED
    db.session.commit()
    login(data["pm_a"])
    client.post(f"/orders/{data['order']}/delete")
    assert fresh(Order, data["order"]) is not None


def test_other_pm_cannot_delete(client, login, data):
    login(data["pm_b"])
    assert client.post(f"/orders/{data['order']}/delete").status_code == 403


def test_admin_updates_order_and_pm_notified(client, login, data, sent_emails):
    login(data["admin"])
    resp = client.post(
        f"/orders/{data['order']}/edit",
        data={
            "status": "SHIPPED",
            "urgency": "IMMEDIATE",
            "shipping_speed": "OVERNIGHT",
            "courier": "UPS",
            "tracking_url": "ups.com/track?x=1",
            "shipping_cost": "12.5",
        },
    )
    assert resp.status_code == 302
    order = fresh(Order, data["order"])
    assert order.status is Status.SHIPPED
    assert order.tracking_url == "https://ups.com/track?x=1"
    assert order.total == Decimal("13.50")
    assert sent_emails == [(["pm.a@example.com"], f"Order #{order.id} is now shipped")]


def test_no_email_when_status_unchanged(client, login, data, sent_emails):
    login(data["admin"])
    client.post(
        f"/orders/{data['order']}/edit",
        data={
            "status": "PENDING",
            "urgency": "IMMEDIATE",
            "shipping_speed": "GROUND",
            "courier": "",
            "shipping_cost": "0",
        },
    )
    assert sent_emails == []


def test_canceled_orders_excluded_from_project_total(client, login, data):
    order = db.session.get(Order, data["order"])
    assert order.project.total == Decimal("1.00")
    order.status = Status.CANCELED
    db.session.commit()
    assert order.project.total == 0


@pytest.mark.parametrize("bad", ["javascript:alert(1)", "data:text/html,x", "https://"])
def test_normalize_url_rejects_unsafe(bad):
    with pytest.raises(ValueError):
        normalize_url(bad)


def test_project_page_renders(client, login, data):
    login(data["pm_a"])
    resp = client.get(f"/projects/{data['a']}")
    assert resp.status_code == 200
    assert b"Digi-Key" in resp.data and b"$1.00" in resp.data
