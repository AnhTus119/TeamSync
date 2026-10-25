"""Hàm dùng chung cho test. App dùng SQLite trong bộ nhớ, seed sẵn dữ liệu mẫu."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app  # noqa: E402


def make_client():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    assert app.test_cli_runner().invoke(args=["seed"]).exit_code == 0
    return app, app.test_client()


class Api:
    def __init__(self, client):
        self.c = client

    def login(self, who, pw="123456"):
        r = self.c.post("/api/auth/login", json={"email": f"{who}@teamsync.local", "password": pw})
        assert r.status_code == 200, r.get_json()
        return r.get_json()["data"]

    def __call__(self, method, url, json=None, status=200, code=None, **kw):
        r = self.c.open(url, method=method, json=json, **kw)
        body = r.get_json(silent=True)
        assert r.status_code == status, f"{method} {url} → {r.status_code} {body}, mong đợi {status}"
        if code:
            assert body["error"]["code"] == code, body
        return body.get("data") if isinstance(body, dict) else r
