"""Application configuration loaded from environment variables."""
import os
from dotenv import load_dotenv

# Load .env from backend folder so it works regardless of where the app is run from
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Flask
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///mailflow.db")

# Google OAuth – place your credentials.json in the backend directory or set
# GOOGLE_CREDENTIALS_FILE to the full path.
GOOGLE_CREDENTIALS_FILE = os.getenv(
    "GOOGLE_CREDENTIALS_FILE",
    os.path.join(os.path.dirname(__file__), "credentials.json"),
)
GOOGLE_TOKEN_FILE = os.getenv(
    "GOOGLE_TOKEN_FILE",
    os.path.join(os.path.dirname(__file__), "token.json"),
)

# Gmail API OAuth scopes required by MailFlow
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

# Google Gemini (optional – used for AI-powered categorisation and reply generation)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Email fetch limits
EMAIL_FETCH_LIMIT = int(os.getenv("EMAIL_FETCH_LIMIT", "50"))
