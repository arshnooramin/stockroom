import pytest

from stockroom import create_app
from stockroom.extensions import db
from stockroom.models import Role, User


def test_anonymous_redirected_to_login(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/auth/login" in resp.location


def test_dev_login_known_user(client, data):
    resp = client.post("/auth/login/dev", data={"email": "PM.A@example.com"})
    assert resp.status_code == 302
    assert client.get("/").location.endswith(f"/projects/{data['a']}")


def test_dev_login_unknown_user_rejected(client, data):
    resp = client.post(
        "/auth/login/dev", data={"email": "stranger@example.com"}, follow_redirects=True
    )
    assert b"hasn&#39;t been given access" in resp.data


def test_superuser_bootstrapped_on_first_login(client, app):
    client.post("/auth/login/dev", data={"email": "boss@example.com"})
    user = db.session.scalar(db.select(User).filter_by(email="boss@example.com"))
    assert user.is_superuser and user.role is Role.ADMIN


def test_allowed_domains_enforced(client, app, data):
    app.config["ALLOWED_EMAIL_DOMAINS"] = ["school.edu"]
    resp = client.post("/auth/login/dev", data={"email": "pm.a@example.com"}, follow_redirects=True)
    assert b"domain isn&#39;t allowed" in resp.data


def test_dev_login_disabled_returns_404(client, app):
    app.config["DEV_LOGIN"] = False
    assert client.post("/auth/login/dev", data={"email": "x@example.com"}).status_code == 404


def test_dev_login_refused_outside_debug(monkeypatch):
    monkeypatch.setenv("DEV_LOGIN", "true")
    monkeypatch.setenv("SECRET_KEY", "x")
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    with pytest.raises(RuntimeError, match="DEV_LOGIN"):
        create_app()


def test_secret_key_required_in_production(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app()


def test_open_redirect_blocked(client, data):
    client.get("/auth/login?next=//evil.example.com")
    resp = client.post("/auth/login/dev", data={"email": "pm.a@example.com"})
    assert "evil" not in resp.location


def test_next_honored(client, data):
    client.get(f"/auth/login?next=/projects/{data['a']}")
    resp = client.post("/auth/login/dev", data={"email": "pm.a@example.com"})
    assert resp.location.endswith(f"/projects/{data['a']}")


def test_logout_requires_post(client, login, data):
    login(data["pm_a"])
    assert client.get("/auth/logout").status_code == 405
    assert client.post("/auth/logout").status_code == 302
    assert client.get("/").status_code == 302
