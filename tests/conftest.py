from decimal import Decimal

import pytest

from stockroom import create_app
from stockroom.extensions import db
from stockroom.models import Item, Order, Project, Role, ShippingSpeed, Urgency, User


@pytest.fixture(autouse=True)
def _ignore_dotenv(monkeypatch):
    # Tests must not pick up a developer's local .env.
    monkeypatch.setattr("stockroom.load_dotenv", lambda: None)


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "WTF_CSRF_ENABLED": False,
            "DEV_LOGIN": True,
            "SUPERUSER_EMAIL": "boss@example.com",
            "ALLOWED_EMAIL_DOMAINS": [],
            "OIDC_CLIENT_ID": None,
            "RESEND_API_KEY": None,
            "MAIL_SERVER": None,
        }
    )
    with app.app_context():
        db.create_all()
        yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sent_emails(monkeypatch):
    sent = []
    monkeypatch.setattr(
        "stockroom.notifications.send_email",
        lambda to, subject, body: sent.append((sorted(to), subject)),
    )
    return sent


@pytest.fixture
def data(app):
    """Two projects, each with a PM, plus an admin. Project A has one pending order."""
    a, b = Project(name="Project A"), Project(name="Project B")
    admin = User(email="admin@example.com", name="Ada Admin", role=Role.ADMIN)
    pm_a = User(email="pm.a@example.com", name="Pat A", role=Role.PM, project=a)
    pm_b = User(email="pm.b@example.com", name="Pat B", role=Role.PM, project=b)
    order = Order(
        project=a,
        created_by=pm_a,
        vendor="Digi-Key",
        vendor_url="https://www.digikey.com",
        urgency=Urgency.IMMEDIATE,
        shipping_speed=ShippingSpeed.GROUND,
        items=[
            Item(
                description="Resistor",
                part_number="R-1",
                unit_price=Decimal("0.10"),
                quantity=10,
                justification="Pull-ups",
            )
        ],
    )
    db.session.add_all([a, b, admin, pm_a, pm_b, order])
    db.session.commit()
    return {
        "a": a.id,
        "b": b.id,
        "admin": admin.id,
        "pm_a": pm_a.id,
        "pm_b": pm_b.id,
        "order": order.id,
    }


@pytest.fixture
def login(client):
    def _login(user_id: int):
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

    return _login
