from dotenv import load_dotenv
from flask import Flask, abort, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from stockroom import admin, auth, cli, filters, orders, projects
from stockroom.config import load_config
from stockroom.extensions import csrf, db, login_manager
from stockroom.models import Courier, ShippingSpeed, Status, Urgency


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _):
    if type(dbapi_connection).__module__.startswith("sqlite3"):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")


def create_app(test_config: dict | None = None) -> Flask:
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(load_config())
    if test_config:
        app.config.update(test_config)

    if not app.config["SECRET_KEY"]:
        if not (app.debug or app.testing):
            raise RuntimeError("SECRET_KEY must be set in production.")
        app.config["SECRET_KEY"] = "dev-only-insecure-key"
    if app.config["DEV_LOGIN"] and not (app.debug or app.testing):
        raise RuntimeError(
            "DEV_LOGIN lets anyone sign in as any user; it only works in debug mode."
        )
    if not (app.debug or app.testing):
        app.config.update(SESSION_COOKIE_SECURE=True, REMEMBER_COOKIE_SECURE=True)
    app.config.update(SESSION_COOKIE_SAMESITE="Lax")

    # Hosting platforms terminate TLS at a proxy; trust its headers so redirect URLs use https.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"
    auth.init_oauth(app)
    cli.init_app(app)
    filters.init_app(app)

    for module in (auth, admin, projects, orders):
        app.register_blueprint(module.bp)

    app.jinja_env.globals.update(
        Status=Status, Urgency=Urgency, ShippingSpeed=ShippingSpeed, Courier=Courier
    )

    @app.get("/")
    @login_required
    def index():
        if current_user.is_admin:
            return redirect(url_for("admin.index"))
        if current_user.project_id is None:
            abort(403)
        return redirect(url_for("projects.show", project_id=current_user.project_id))

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.errorhandler(HTTPException)
    def http_error(err: HTTPException):
        return render_template("error.html", error=err), err.code

    return app
