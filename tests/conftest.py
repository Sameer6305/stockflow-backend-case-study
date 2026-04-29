"""Pytest fixtures for the StockFlow test suite."""

from __future__ import annotations

import pytest

from stockflow.app_factory import create_app
from stockflow.database.session import drop_database, init_database
from stockflow.extensions import db


@pytest.fixture()
def app():
    app = create_app()
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )

    with app.app_context():
        init_database(app)
        yield app
        drop_database(app)


@pytest.fixture()
def client(app):
    return app.test_client()
