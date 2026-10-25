"""Sinh Postman collection từ chính các route Flask → collection luôn khớp code, không ai phải sửa tay phần khung.

    python scripts/gen_postman.py
Ghi ra tests/postman/TeamSync.skeleton.postman_collection.json (+ environment). Import cả 2 file vào Postman.
File skeleton chỉ là khung. File chính TeamSync.postman_collection.json do TV3 quản lý (import skeleton → bổ sung ví dụ, test → Export).
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "tests" / "postman"
FOLDERS = {"m20_api": "M20 — Tài khoản, workspace, phân quyền", "m06_api": "M06 — Dự án, cột mốc, nhiệm vụ",
           "m17_api": "M17 — Dashboard, báo cáo, đánh giá"}
VARS = {"base_url": "http://127.0.0.1:5000", "workspace_id": "1", "project_id": "1", "task_id": "1",
        "milestone_id": "1", "user_id": "4", "invitation_id": "1", "comment_id": "1", "template_id": "1",
        "attachment_id": "1", "depends_on_id": "1", "token": "paste-token-here"}


def to_postman_path(rule):
    return re.sub(r"<(?:\w+:)?(\w+)>", r"{{\1}}", rule)


def request(name, method, path, body=None):
    url = "{{base_url}}" + path
    item = {"name": name, "request": {"method": method, "header": [], "url": {
        "raw": url, "host": ["{{base_url}}"], "path": [p for p in path.split("/") if p]}}}
    if body is not None:
        item["request"]["header"] = [{"key": "Content-Type", "value": "application/json"}]
        item["request"]["body"] = {"mode": "raw", "raw": json.dumps(body, ensure_ascii=False, indent=2)}
    return item


def main():
    app = create_app()
    folders = {k: [] for k in FOLDERS}
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        bp = rule.endpoint.split(".")[0]
        if bp not in folders:
            continue
        for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            doc = (app.view_functions[rule.endpoint].__doc__ or "").strip().splitlines()
            name = f"{method} {rule.rule}"
            item = request(name, method, to_postman_path(rule.rule), {} if method in ("POST", "PATCH") else None)
            if doc:
                item["request"]["description"] = "\n".join(doc)
            folders[bp].append(item)
    logins = [request(f"Đăng nhập: {who}", "POST", "/api/auth/login",
                      {"email": f"{who}@teamsync.local", "password": "123456"})
              for who in ("admin", "gv", "sv1", "sv2", "sv4")]
    collection = {
        "info": {"name": "TeamSync API", "schema":
                 "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
                 "description": "Đăng nhập trước (Postman tự giữ cookie session), rồi gọi API. Đổi vai trò = gọi lại request Đăng nhập khác."},
        "item": [{"name": "00 — Đăng nhập theo vai trò", "item": logins}]
                + [{"name": FOLDERS[k], "item": v} for k, v in folders.items()],
    }
    env = {"name": "TeamSync local", "values": [{"key": k, "value": v, "enabled": True} for k, v in VARS.items()]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "TeamSync.skeleton.postman_collection.json").write_text(json.dumps(collection, ensure_ascii=False, indent=2), "utf-8")
    (OUT / "TeamSync.postman_environment.json").write_text(json.dumps(env, ensure_ascii=False, indent=2), "utf-8")
    print(f"Đã sinh {sum(len(v) for v in folders.values())} request vào {OUT}")


if __name__ == "__main__":
    main()
