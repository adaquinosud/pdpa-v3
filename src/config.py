"""Configurações do Flask app."""

import os
from dotenv import load_dotenv

from src.utils.db_url import normalize_db_url

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-key")
    # normalize_db_url: Render/Heroku entregam postgresql:// → força psycopg3.
    SQLALCHEMY_DATABASE_URI = normalize_db_url(
        os.getenv("DATABASE_URL", "sqlite:///pdpa_v3_dev.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  # Gemini (Reputação em IA)
    APIFY_TOKEN = os.getenv("APIFY_TOKEN")
    FERNET_KEY = os.getenv("FERNET_KEY")

    # Cookie de sessão (login = Flask session assinada). HTTPONLY + SameSite=Lax
    # são seguros e incondicionais (app server-rendered, same-origin). SECURE é
    # condicional ao ambiente — ver Dev/ProductionConfig (Secure=True exige HTTPS,
    # quebraria o login em http://localhost no dev).
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Classifier — escalada Haiku→Sonnet (Frente 3 do Bloco 3.1)
    CLASSIFIER_ESCALATION_ENABLED = (
        os.getenv("CLASSIFIER_ESCALATION_ENABLED", "true").lower() == "true"
    )
    CLASSIFIER_ESCALATION_THRESHOLD = float(os.getenv("CLASSIFIER_ESCALATION_THRESHOLD", "0.6"))
    CLASSIFIER_MONTHLY_BUDGET_USD = float(os.getenv("CLASSIFIER_MONTHLY_BUDGET_USD", "50.0"))
    CLASSIFIER_SONNET_MODEL = os.getenv("CLASSIFIER_SONNET_MODEL", "claude-sonnet-4-5-20250929")


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False  # http://localhost no dev — sem HTTPS


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # exige HTTPS — cookie só vai por conexão segura


def get_config():
    env = os.getenv("FLASK_ENV", "development")
    return ProductionConfig() if env == "production" else DevelopmentConfig()
