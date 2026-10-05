from stockroom.demo import seed_demo
from stockroom.extensions import db
from stockroom.models import Order, Project, Role, User


def count(model):
    return db.session.scalar(db.select(db.func.count()).select_from(model))


def test_seed_demo_populates_empty_db(app):
    assert seed_demo() is True
    assert count(Project) == 3
    assert count(Order) == 5
    boss = db.session.scalar(db.select(User).filter_by(email="boss@example.com"))
    assert boss.is_superuser and boss.role is Role.ADMIN
    assert boss.name == "Boss"


def test_seed_demo_skips_when_data_exists(app):
    seed_demo()
    assert seed_demo() is False
    assert count(Project) == 3


def test_seed_demo_cli(app):
    result = app.test_cli_runner().invoke(args=["seed-demo"])
    assert "Demo data added" in result.output
    result = app.test_cli_runner().invoke(args=["seed-demo"])
    assert "skipped" in result.output


def test_seeded_pages_render(app, client, login):
    seed_demo()
    boss = db.session.scalar(db.select(User).filter_by(email="boss@example.com"))
    login(boss.id)
    assert client.get("/admin/").status_code == 200
    for project in db.session.scalars(db.select(Project)):
        assert client.get(f"/projects/{project.id}").status_code == 200
