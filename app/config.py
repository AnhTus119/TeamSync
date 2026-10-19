import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///teamsync.db")
    JSON_AS_ASCII = False  # trả tiếng Việt không bị escape
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB / file minh chứng
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    RISK_DAYS_BEFORE_DUE = int(os.getenv("RISK_DAYS_BEFORE_DUE", 2))
    RISK_DAYS_NO_UPDATE = int(os.getenv("RISK_DAYS_NO_UPDATE", 3))
