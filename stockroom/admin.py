import re
from datetime import UTC, datetime
from decimal import Decimal

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user
from sqlalchemy.orm import selectinload

from stockroom.auth import admin_required, superuser_required
from stockroom.export import build_workbook
from stockroom.extensions import db
from stockroom.models import IN_PROGRESS, Item, Order, Project, Role, Status, User

bp = Blueprint("admin", __name__, url_prefix="/admin")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _projects_with_orders(ids: list[int] | None = None) -> list[Project]:
    query = (
        db.select(Project)
        .options(
            selectinload(Project.orders).selectinload(Order.items),
            selectinload(Project.members),
        )
        .order_by(Project.name)
    )
    if ids is not None:
        query = query.where(Project.id.in_(ids))
    return list(db.session.scalars(query))


def _add_user(form, role: Role, project: Project | None = None) -> None:
    name = form.get("name", "").strip()
    email = form.get("email", "").strip().lower()
    domains = current_app.config["ALLOWED_EMAIL_DOMAINS"]
    if not name or not EMAIL_RE.match(email):
        flash("Enter a name and a valid email address.", "danger")
    elif domains and email.rpartition("@")[2] not in domains:
        flash(f"Email must be at one of: {', '.join(domains)}.", "danger")
    elif db.session.scalar(db.select(User.id).filter_by(email=email)):
        flash(f"{email} already has access.", "danger")
    else:
        db.session.add(User(name=name, email=email, role=role, project=project))
        db.session.commit()
        flash(f"Added {name} as {role.value.lower()}.", "success")


@bp.get("/")
@admin_required
def index():
    admins = db.session.scalars(db.select(User).filter_by(role=Role.ADMIN).order_by(User.name))
    projects = _projects_with_orders()
    stats = {
        "spend": sum((p.total for p in projects), Decimal("0")),
        "pending": sum(p.count(Status.PENDING) for p in projects),
        "in_progress": sum(p.count(*IN_PROGRESS) for p in projects),
        "managers": sum(len(p.members) for p in projects),
    }
    return render_template("admin/index.html", projects=projects, admins=list(admins), stats=stats)


@bp.post("/projects")
@admin_required
def create_project():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Project name is required.", "danger")
    else:
        db.session.add(Project(name=name))
        db.session.commit()
        flash(f"Created project {name}.", "success")
    return redirect(url_for("admin.index"))


@bp.post("/projects/<int:project_id>/delete")
@admin_required
def delete_project(project_id: int):
    project = db.get_or_404(Project, project_id)
    name = project.name
    db.session.delete(project)
    db.session.commit()
    flash(f"Deleted project {name} with its orders and project managers.", "success")
    return redirect(url_for("admin.index"))


@bp.post("/members")
@admin_required
def add_member():
    _add_user(
        request.form, Role.PM, db.get_or_404(Project, request.form.get("project_id", type=int))
    )
    return redirect(url_for("admin.index"))


@bp.post("/admins")
@superuser_required
def add_admin():
    _add_user(request.form, Role.ADMIN)
    return redirect(url_for("admin.index"))


@bp.post("/users/<int:user_id>/delete")
@admin_required
def delete_user(user_id: int):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id or user.is_superuser:
        abort(403)
    if user.is_admin and not current_user.is_superuser:
        abort(403)
    name = user.name
    db.session.delete(user)
    db.session.commit()
    flash(f"Removed {name}.", "success")
    return redirect(url_for("admin.index"))


@bp.post("/export")
@admin_required
def export():
    ids = None if request.form.get("all") else request.form.getlist("project_id", type=int)
    if ids == []:
        flash("Select at least one project to export.", "danger")
        return redirect(url_for("admin.index"))
    stamp = datetime.now(UTC).strftime("%Y-%m-%d-%H%M")
    return send_file(
        build_workbook(_projects_with_orders(ids)),
        as_attachment=True,
        download_name=f"stockroom-orders-{stamp}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.post("/reset")
@superuser_required
def reset():
    if request.form.get("confirm") != "RESET":
        flash("Type RESET to confirm.", "danger")
        return redirect(url_for("admin.index"))
    db.session.execute(db.delete(Item))
    db.session.execute(db.delete(Order))
    db.session.execute(db.delete(User).where(User.role == Role.PM))
    db.session.execute(db.delete(Project))
    db.session.commit()
    flash("Deleted all projects, orders and project managers. Admins were kept.", "success")
    return redirect(url_for("admin.index"))
