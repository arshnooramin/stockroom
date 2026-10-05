from functools import wraps

from authlib.integrations.base_client import OAuthError
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from stockroom.extensions import db, login_manager, oauth
from stockroom.models import Role, User

bp = Blueprint("auth", __name__, url_prefix="/auth")


def init_oauth(app):
    oauth.init_app(app)
    if app.config["OIDC_CLIENT_ID"]:
        oauth.register(
            "oidc",
            client_id=app.config["OIDC_CLIENT_ID"],
            client_secret=app.config["OIDC_CLIENT_SECRET"],
            server_metadata_url=app.config["OIDC_DISCOVERY_URL"],
            client_kwargs={"scope": "openid email profile"},
        )


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))


def sso_client():
    return oauth.create_client("oidc")


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def superuser_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_superuser:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def _safe_next(target: str | None) -> str | None:
    # Only allow same-site relative paths so the login flow can't be used as an open redirect.
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


def _complete_login(email: str):
    email = email.strip().lower()
    domains = current_app.config["ALLOWED_EMAIL_DOMAINS"]
    if domains and email.rpartition("@")[2] not in domains:
        flash("That account's email domain isn't allowed here.", "danger")
        return redirect(url_for("auth.login"))

    user = db.session.scalar(db.select(User).filter_by(email=email))
    if user is None and email == current_app.config["SUPERUSER_EMAIL"]:
        user = User(email=email, name=email.partition("@")[0], role=Role.ADMIN, is_superuser=True)
        db.session.add(user)
        db.session.commit()
    if user is None:
        flash(
            f"{email} hasn't been given access yet. Ask an administrator to add you to a project.",
            "danger",
        )
        return redirect(url_for("auth.login"))

    login_user(user)
    return redirect(_safe_next(session.pop("next", None)) or url_for("index"))


@bp.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if nxt := _safe_next(request.args.get("next")):
        session["next"] = nxt
    return render_template(
        "auth/login.html",
        sso_enabled=sso_client() is not None,
        dev_login=current_app.config["DEV_LOGIN"],
    )


@bp.get("/login/sso")
def login_sso():
    client = sso_client() or abort(404)
    return client.authorize_redirect(url_for("auth.callback", _external=True))


@bp.get("/callback")
def callback():
    client = sso_client() or abort(404)
    try:
        token = client.authorize_access_token()
    except OAuthError as err:
        current_app.logger.warning("OIDC login failed: %s", err)
        flash("Sign-in failed. Please try again.", "danger")
        return redirect(url_for("auth.login"))

    info = token.get("userinfo") or client.userinfo(token=token)
    if not info.get("email") or info.get("email_verified") is False:
        flash("Your identity provider didn't return a verified email address.", "danger")
        return redirect(url_for("auth.login"))
    return _complete_login(info["email"])


@bp.post("/login/dev")
def login_dev():
    if not current_app.config["DEV_LOGIN"]:
        abort(404)
    return _complete_login(request.form.get("email", ""))


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
