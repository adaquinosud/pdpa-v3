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


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


def get_config():
    env = os.getenv("FLASK_ENV", "development")
    return ProductionConfig() if env == "production" else DevelopmentConfig()
