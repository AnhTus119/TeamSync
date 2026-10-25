"""Đánh giá luật cảnh báo rủi ro trên dữ liệu đã seed (hướng nghiên cứu của đề tài).

    flask --app run seed
    python scripts/evaluate_risks.py

Chạy lại luật từng ngày trên lịch sử của mọi dự án và in: số việc trễ, bao nhiêu việc trễ được cảnh báo
trước hạn (recall), cảnh báo sớm trung bình bao nhiêu ngày, và tỷ lệ cảnh báo thừa trên việc đúng hạn.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app  # noqa: E402
from app.m17_reports.risk import evaluate  # noqa: E402
from app.models import Project  # noqa: E402


def pct(x):
    return "—" if x is None else f"{x * 100:.0f}%"


def main():
    app = create_app()
    with app.app_context():
        all_tasks = []
        print(f"{'Dự án':45} {'Trễ':>4} {'Báo trước':>9} {'Recall':>7} {'Sớm (ngày)':>10} {'Đúng hạn':>8} {'Báo thừa':>8}")
        for p in Project.query.order_by(Project.id):
            r = evaluate(p.tasks)
            all_tasks += p.tasks
            print(f"{p.name[:45]:45} {r['late_tasks']:>4} {r['late_warned_before_due']:>9} {pct(r['recall']):>7} "
                  f"{r['avg_lead_days'] if r['avg_lead_days'] is not None else '—':>10} {r['on_time_tasks']:>8} "
                  f"{pct(r['false_alarm_rate']):>8}")
        r = evaluate(all_tasks)
        print("-" * 98)
        print(f"{'TỔNG':45} {r['late_tasks']:>4} {r['late_warned_before_due']:>9} {pct(r['recall']):>7} "
              f"{r['avg_lead_days'] if r['avg_lead_days'] is not None else '—':>10} {r['on_time_tasks']:>8} "
              f"{pct(r['false_alarm_rate']):>8}")
        print(f"\nNgưỡng: RISK_DAYS_BEFORE_DUE={app.config['RISK_DAYS_BEFORE_DUE']}, "
              f"RISK_DAYS_NO_UPDATE={app.config['RISK_DAYS_NO_UPDATE']}, RISK_RETURN_COUNT={app.config['RISK_RETURN_COUNT']}"
              " — đổi trong .env rồi chạy lại để so sánh.")


if __name__ == "__main__":
    main()
