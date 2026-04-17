import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# Use /tmp on serverless (Vercel), otherwise use local data/
IS_SERVERLESS = os.getenv("VERCEL", "") == "1"
if IS_SERVERLESS:
    DATA_DIR = Path("/tmp/kol_data")
else:
    DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'kol_hunter.db'}")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

# Email
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "gmail")
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY", "")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN", "")

SENDER_NAME = os.getenv("SENDER_NAME", "Market Team")
SENDER_TITLE = os.getenv("SENDER_TITLE", "Partnership Manager")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")

# Twitter/X
X_USERNAME = os.getenv("X_USERNAME", "")
X_PASSWORD = os.getenv("X_PASSWORD", "")
X_EMAIL = os.getenv("X_EMAIL", "")

# Scraping defaults
DEFAULT_RATE_LIMIT = 3.0  # seconds between requests
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30

# Scoring weights
SCORING_WEIGHTS = {
    "reach": 0.20,
    "engagement": 0.25,
    "relevance": 0.25,
    "region": 0.15,
    "recency": 0.05,
    "competitor": 0.10,
}
