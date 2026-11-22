import click, time
from datetime import datetime, timedelta
from flask import current_app
from flask.cli import with_appcontext
from ..extensions import db
from ..models.academic import RuntimeSetting
from ..common.clock import iso, utcnow


@click.group("demo-clock")
def demo_clock():
    pass


@demo_clock.command("set")
@click.option("--offset-hours", type=float, required=True)
@with_appcontext
def set_clock(offset_hours):
    require_demo()
    fixture = db.session.get(RuntimeSetting, "demo_fixture")
    if not fixture:
        raise click.ClickException("Chạy seed-demo trước")
    at = datetime.fromisoformat(fixture.value["t0"]) + timedelta(hours=offset_hours)
    r = db.session.get(RuntimeSetting, "demo_clock")
    if not r:
        r = RuntimeSetting(key="demo_clock", value={})
        db.session.add(r)
    r.value = {"at": at.isoformat()}
    db.session.commit()
    click.echo(iso(at))


def require_demo():
    if current_app.config["APP_ENV"] not in (
        "development",
        "test",
    ) or not current_app.config.get("DEMO_CLOCK_ENABLED"):
        raise click.ClickException(
            "Chỉ dùng khi APP_ENV=development/test và DEMO_CLOCK_ENABLED=1"
        )


@demo_clock.command("live")
@with_appcontext
def live_clock():
    """Resume the actual system clock after a timed demo scenario."""
    require_demo()
    row = db.session.get(RuntimeSetting, "demo_clock")
    if row:
        row.value = {}
        db.session.commit()
    click.echo("Đang dùng thời gian thực của hệ thống")


def register_cli(app):
    app.cli.add_command(demo_clock)
    app.cli.add_command(create_operator)

    @app.cli.command("seed-demo")
    def seed_demo_command():
        require_demo()
        from .workflow_seed import seed_demo

        seed_demo()
        click.echo("Dữ liệu demo đã sẵn sàng. Mật khẩu development: 12345")

    @app.cli.command("seed-showcase")
    def showcase_command():
        require_demo()
        from .showcase import seed_showcase
        click.echo("Đã nạp dữ liệu minh họa" if seed_showcase() else "Dữ liệu minh họa đã tồn tại")

    @app.cli.command("risk-evaluate")
    @click.option("--course", default=None)
    def risk_evaluate(course):
        from ..common.jobs import evaluate_all

        click.echo(f"Detected: {evaluate_all(course)}")

    @app.cli.command("worker")
    @click.option("--once", is_flag=True)
    def worker(once):
        from ..common.jobs import dispatch_outbox, evaluate_all

        last = -900
        while True:
            if time.monotonic() - last >= 900:
                evaluate_all()
                last = time.monotonic()
            dispatch_outbox()
            if once:
                break
            time.sleep(5)

    @app.cli.command("cleanup-storage")
    def cleanup_storage():
        from ..common.storage import root
        from ..models.academic import EvidenceAsset, AppealEvidence

        keep = {
            x[0]
            for x in db.session.query(EvidenceAsset.storage_key).filter(
                EvidenceAsset.storage_key != None
            )
        } | {x[0] for x in db.session.query(AppealEvidence.storage_key)}
        removed = 0
        for p in root().iterdir():
            if (
                p.is_file()
                and not p.is_symlink()
                and p.name not in keep
                and time.time() - p.stat().st_mtime > 86400
            ):
                p.unlink()
                removed += 1
        click.echo(f"Removed orphan files: {removed}")


@click.command("create-operator")
@click.option("--email", required=True)
@click.option("--name", required=True)
@click.password_option(confirmation_prompt=True)
@with_appcontext
def create_operator(email, name, password):
    from ..models import User

    if len(password) < 12 or "@" not in email:
        raise click.ClickException("Email hợp lệ và mật khẩu ít nhất 12 ký tự")
    if User.query.filter_by(email=email.lower()).first():
        raise click.ClickException("Tài khoản đã tồn tại")
    u = User(email=email.lower(), full_name=name, role="admin")
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    click.echo("Đã tạo tài khoản vận hành")
