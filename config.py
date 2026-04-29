"""Application configuration for StockFlow.

The project uses a lightweight configuration layer so the app factory can be
kept clean and environment-specific settings stay centralized.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SQLITE_PATH = (BASE_DIR / "stockflow.db").as_posix()


class BaseConfig:
    """Shared configuration used by all environments."""

    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")
    JSON_SORT_KEYS = False
    JSONIFY_PRETTYPRINT_REGULAR = True
    API_VERSION = "v1"
    SERVICE_NAME = "StockFlow"


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    WTF_CSRF_ENABLED = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config() -> type[BaseConfig]:
    """Resolve the active config class from the environment."""

    environment_name = os.getenv("FLASK_ENV", "development").lower()
    return CONFIG_MAP.get(environment_name, DevelopmentConfig)
