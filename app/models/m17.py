"""Bảng của M17 — Dashboard, báo cáo và đánh giá. Chủ sở hữu: Thành viên 3.
M17 chỉ ĐỌC bảng của M06; bảng duy nhất M17 ghi là PeerReview."""
from ..common.utils import iso, now
from ..extensions import db


class PeerReview(db.Model):
    __tablename__ = "peer_review"
    __table_args__ = (db.UniqueConstraint("project_id", "reviewer_id", "reviewee_id"),
                      db.CheckConstraint("score BETWEEN 1 AND 5"))
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reviewee_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    def to_dict(self, hide_reviewer=True):
        d = {"id": self.id, "project_id": self.project_id, "reviewee_id": self.reviewee_id,
             "score": self.score, "comment": self.comment, "created_at": iso(self.created_at)}
        if not hide_reviewer:
            d["reviewer_id"] = self.reviewer_id
        return d
