from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required
from sqlalchemy.orm import selectinload

from stockroom.extensions import db
from stockroom.models import IN_PROGRESS, Order, Project

bp = Blueprint("projects", __name__, url_prefix="/projects")


def get_project_or_404(project_id: int) -> Project:
    project = db.session.get(
        Project,
        project_id,
        options=[
            selectinload(Project.orders).selectinload(Order.items),
            selectinload(Project.members),
        ],
    )
    if project is None:
        abort(404)
    if not current_user.can_access(project):
        abort(403)
    return project


@bp.get("/<int:project_id>")
@login_required
def show(project_id: int):
    return render_template(
        "projects/show.html", project=get_project_or_404(project_id), IN_PROGRESS=IN_PROGRESS
    )
