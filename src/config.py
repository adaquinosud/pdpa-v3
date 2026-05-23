"""Configurações do Flask app."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///pdpa_v3_dev.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    APIFY_TOKEN = os.getenv("APIFY_TOKEN")
    FERNET_KEY = os.getenv("FERNET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-key")
    JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", 24))

    # Classifier — escalada Haiku→Sonnet (Frente 3 do Bloco 3.1)
    CLASSIFIER_ESCALATION_ENABLED = (
        os.getenv("CLASSIFIER_ESCALATION_ENABLED", "true").lower() == "true"
    )
    CLASSIFIER_ESCALATION_THRESHOLD = float(os.getenv("CLASSIFIER_ESCALATION_THRESHOLD", "0.6"))
    CLASSIFIER_MONTHLY_BUDGET_USD = float(os.getenv("CLASSIFIER_MONTHLY_BUDGET_USD", "50.0"))
    CLASSIFIER_SONNET_MODEL = os.getenv("CLASSIFIER_SONNET_MODEL", "claude-sonnet-4-5-20250929")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


def get_config():
    env = os.getenv("FLASK_ENV", "development")
    return ProductionConfig() if env == "production" else DevelopmentConfig()
