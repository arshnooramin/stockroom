import click

from stockroom import demo
from stockroom.extensions import db
from stockroom.models import Role, User


def init_app(app):
    app.cli.add_command(init_db)
    app.cli.add_command(seed_demo)
    app.cli.add_command(create_admin)


@click.command("init-db")
def init_db():
    """Create any missing tables. Safe to run on every deploy; existing data is untouched."""
    db.create_all()
    click.echo("Database ready.")


@click.command("seed-demo")
def seed_demo():
    """Fill an empty database with a superuser, an admin and sample projects."""
    if demo.seed_demo():
        click.echo("Demo data added.")
    else:
        click.echo("Database already has projects; skipped demo data.")


@click.command("create-admin")
@click.argument("email")
@click.option("--name", help="Display name (defaults to the part of the email before @).")
@click.option("--superuser", is_flag=True, help="Can manage admins and reset data.")
def create_admin(email: str, name: str | None, superuser: bool):
    """Grant EMAIL admin access, creating or promoting the user."""
    email = email.strip().lower()
    user = db.session.scalar(db.select(User).filter_by(email=email))
    if user is None:
        user = User(email=email, name=name or email.partition("@")[0])
        db.session.add(user)
    user.role, user.project, user.is_superuser = (
        Role.ADMIN,
        None,
        bool(superuser or user.is_superuser),
    )
    if name:
        user.name = name
    db.session.commit()
    click.echo(f"{email} is now {'a superuser' if user.is_superuser else 'an admin'}.")
