import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    APP_ENV = os.getenv("APP_ENV", "development")
    DEMO_CLOCK_ENABLED = os.getenv("DEMO_CLOCK_ENABLED", "0") == "1"
    CSRF_ENABLED = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("APP_ENV") == "production"
    PRIVATE_STORAGE = os.getenv("PRIVATE_STORAGE", "instance/private")
    MAX_FILE_BYTES = 10 * 1024 * 1024
    MAX_REVISION_BYTES = 50 * 1024 * 1024
    MAX_PROJECT_BYTES = 500 * 1024 * 1024
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///teamsync.db")
    MAX_CONTENT_LENGTH = 12 * 1024 * 1024  # 10 MB mỗi file minh chứng
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    ALLOWED_EXTENSIONS = {
        "pdf",
        "png",
        "jpg",
        "jpeg",
        "docx",
        "xlsx",
        "pptx",
        "zip",
        "txt",
    }
    MEETING_AI_API_KEY = os.getenv("MEETING_AI_API_KEY", "")
    MEETING_AI_MODEL = os.getenv("MEETING_AI_MODEL", "gpt-4.1-mini")
    # AI lập kế hoạch/timeline: Google Gemini (gói miễn phí). Không có key thì dùng bộ sinh theo quy tắc.
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    SSO_ALLOWED_DOMAINS = [x.strip().lower() for x in os.getenv("SSO_ALLOWED_DOMAINS", "").split(",") if x.strip()]
    JITSI_DOMAIN = os.getenv("JITSI_DOMAIN", "")
    JITSI_APP_ID = os.getenv("JITSI_APP_ID", "")
    JITSI_SECRET = os.getenv("JITSI_SECRET", "")
    JITSI_AUDIENCE = os.getenv("JITSI_AUDIENCE", "jitsi")
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    SOCKETIO_MESSAGE_QUEUE = os.getenv("SOCKETIO_MESSAGE_QUEUE", "")
    # Ngưỡng luật cảnh báo rủi ro (M17)
    RISK_DAYS_BEFORE_DUE = int(os.getenv("RISK_DAYS_BEFORE_DUE", 2))
    RISK_DAYS_NO_UPDATE = int(os.getenv("RISK_DAYS_NO_UPDATE", 3))
    RISK_RETURN_COUNT = int(os.getenv("RISK_RETURN_COUNT", 2))
    # Đèn sức khỏe: đỏ khi số việc quá hạn >= ngưỡng này
    HEALTH_RED_OVERDUE = int(os.getenv("HEALTH_RED_OVERDUE", 2))
