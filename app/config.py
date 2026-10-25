import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///teamsync.db")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB mỗi file minh chứng
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "docx", "xlsx", "pptx", "zip", "txt"}
    # Ngưỡng luật cảnh báo rủi ro (M17)
    RISK_DAYS_BEFORE_DUE = int(os.getenv("RISK_DAYS_BEFORE_DUE", 2))
    RISK_DAYS_NO_UPDATE = int(os.getenv("RISK_DAYS_NO_UPDATE", 3))
    RISK_RETURN_COUNT = int(os.getenv("RISK_RETURN_COUNT", 2))
    # Đèn sức khỏe: đỏ khi số việc quá hạn >= ngưỡng này
    HEALTH_RED_OVERDUE = int(os.getenv("HEALTH_RED_OVERDUE", 2))
