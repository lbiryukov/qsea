from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

import qsea

from ._integration_helpers import MAIN_APP_NAME, QLIK_URL


def _configure_test_logging() -> None:
    logger = logging.getLogger("qsea")
    if logger.handlers:
        return

    Path("logs").mkdir(exist_ok=True)
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler("logs/qsea_pytest.log", mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s\tLineNo:%(lineno)s\t%(funcName)s()\t%(levelname)s: %(message)s"
        )
    )
    logger.addHandler(file_handler)


_configure_test_logging()


@pytest.fixture(scope="session")
def connection_config():
    api_key = os.environ.get("QLIKSENSE_API_KEY")
    if not api_key:
        pytest.skip("QLIKSENSE_API_KEY is required for integration tests.")

    return {"Authorization": api_key}


@pytest.fixture(scope="session")
def connection(connection_config):
    qsea.config.logQueryMaxLength = 10000
    return qsea.Connection(connection_config, QLIK_URL, timeout=60)


@pytest.fixture(scope="session")
def connection_factory(connection_config):
    def _make(timeout: int = 60):
        return qsea.Connection(connection_config, QLIK_URL, timeout=timeout)

    return _make


@pytest.fixture(scope="session")
def app_factory(connection):
    def _make(app_name: str = MAIN_APP_NAME, depth: int | None = None, load: bool = True):
        app = qsea.App(connection, app_name)
        if load:
            if depth is None:
                app.load()
            else:
                app.load(depth=depth)
        return app

    return _make


@pytest.fixture
def name_factory():
    return lambda prefix: f"{prefix}_{os.urandom(4).hex()}"


@pytest.fixture
def cleanup_registry():
    cleanup_actions = []
    yield cleanup_actions
    for action in reversed(cleanup_actions):
        try:
            action()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def clear_selections_after_test(app_factory):
    yield
    try:
        app = app_factory(load=False)
        app.clear_selections()
    except Exception:
        pass
