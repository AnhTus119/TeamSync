"""Đo chất lượng luật cảnh báo rủi ro trên TOÀN BỘ dữ liệu (M17 — Thành viên 3).

    python scripts/evaluate_risks.py                 # dùng database trong .env (instance/teamsync.db)
    python scripts/evaluate_risks.py --memory        # seed lại trong bộ nhớ rồi đo (không đụng DB thật)
    python scripts/evaluate_risks.py --grid          # so sánh nhiều bộ ngưỡng
    python scripts/evaluate_risks.py --grid --csv ket_qua.csv
    python scripts/evaluate_risks.py --due 2 --stale 3 --returns 2     # một bộ ngưỡng cụ thể

Với mỗi bộ ngưỡng, chạy lại luật từng ngày từ lúc tạo việc tới trước hạn và in:
  recall (việc trễ được cảnh báo trước hạn), số ngày cảnh báo sớm trung bình, tỷ lệ cảnh báo thừa trên việc đúng hạn,
  cộng với bảng phân rã theo từng luật. Mặc định ngưỡng lấy từ .env (RISK_DAYS_BEFORE_DUE, RISK_DAYS_NO_UPDATE, RISK_RETURN_COUNT).
"""
import argparse
import csv
import itertools
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app  # noqa: E402
from app.m17_reports import risk, services  # noqa: E402
from app.models import Project  # noqa: E402


def run(datasets, th, today):
    return risk.merge_evaluations([risk.evaluate(d, today, th) for d in datasets])


def fmt(v, suffix=""):
    return "—" if v is None else f"{v}{suffix}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--memory", action="store_true", help="seed lại trong bộ nhớ thay vì dùng DB thật")
    ap.add_argument("--grid", action="store_true", help="so sánh lưới ngưỡng")
    ap.add_argument("--csv", help="ghi kết quả ra file CSV")
    ap.add_argument("--due", type=int, help="RISK_DAYS_BEFORE_DUE")
    ap.add_argument("--stale", type=int, help="RISK_DAYS_NO_UPDATE")
    ap.add_argument("--returns", type=int, help="RISK_RETURN_COUNT")
    args = ap.parse_args()

    cfg = {"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"} if args.memory else None
    app = create_app(cfg)
    if args.memory:
        assert app.test_cli_runner().invoke(args=["seed"]).exit_code == 0
    with app.app_context():
        today = date.today()
        base = services.thresholds()
        datasets = [services.load_project_data(p) for p in Project.query.order_by(Project.id).all()]
        if not datasets:
            sys.exit("Database chưa có dự án. Chạy: flask --app run seed")
        if args.grid:
            combos = list(itertools.product((1, 2, 3, 5), (2, 3, 5, 7), (2, 3)))
        else:
            combos = [(args.due if args.due is not None else base.days_before_due,
                       args.stale if args.stale is not None else base.days_no_update,
                       args.returns if args.returns is not None else base.return_count)]
        rows = []
        print(f"{len(datasets)} dự án, ngày đánh giá {today:%d/%m/%Y}\n")
        print(f"{'sắp tới hạn':>11} {'không cập nhật':>14} {'trả lại ≥':>9} | {'việc trễ':>8} {'đúng hạn':>8} | {'recall':>7} {'sớm TB':>8} {'cảnh báo thừa':>13}")
        for due, stale, ret in combos:
            th = risk.Thresholds(due, stale, ret, base.health_red_overdue)
            m = run(datasets, th, today)
            rows.append({"days_before_due": due, "days_no_update": stale, "return_count": ret,
                         "late_tasks": m["late_tasks"], "on_time_tasks": m["on_time_tasks"], "warned_late": m["warned_late"],
                         "recall_percent": m["recall"], "avg_lead_days": m["avg_lead_days"],
                         "false_alarm_percent": m["false_alarm_rate"], "false_alarm_tasks": m["false_alarm_tasks"]})
            print(f"{due:>11} {stale:>14} {ret:>9} | {m['late_tasks']:>8} {m['on_time_tasks']:>8} | "
                  f"{fmt(m['recall'], '%'):>7} {fmt(m['avg_lead_days'], ' ng'):>8} {fmt(m['false_alarm_rate'], '%'):>13}")
        if not args.grid:
            print("\nPhân rã theo luật (ngưỡng trên):")
            print(f"{'luật':<24} {'việc trễ phát hiện':>18} {'cảnh báo thừa':>14}")
            for code, v in m["per_rule"].items():
                print(f"{risk.RULE_LABELS[code]:<24} {v['late_hit']:>18} {v['on_time_hit']:>14}")
        if args.csv:
            with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
            print(f"\nĐã ghi {len(rows)} dòng vào {args.csv}")


if __name__ == "__main__":
    main()
