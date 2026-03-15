from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import pytest

import qsea

from ._integration_helpers import MAIN_APP_NAME, QLIK_URL

LOGS_DIR = Path("logs")
DETAILED_TEST_LOG_PATH = LOGS_DIR / "qsea_pytest.log"
SHORT_TEST_LOG_PATH = LOGS_DIR / "qsea_pytest_short.log"


def _has_file_handler(logger: logging.Logger, log_file_path: Path) -> bool:
    target_path = log_file_path.resolve()
    for handler in logger.handlers:
        if not isinstance(handler, logging.FileHandler):
            continue
        handler_path = getattr(handler, "baseFilename", None)
        if handler_path and Path(handler_path).resolve() == target_path:
            return True
    return False


def _write_short_test_log(message: str) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    with SHORT_TEST_LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{message}\n")


def _extract_report_message(report: Any) -> str | None:
    longrepr = getattr(report, "longrepr", None)
    reprcrash = getattr(longrepr, "reprcrash", None)
    if reprcrash and getattr(reprcrash, "message", None):
        return str(reprcrash.message)

    longrepr_text = getattr(report, "longreprtext", "") or ""
    lines = [line.strip() for line in longrepr_text.splitlines() if line.strip()]
    if lines:
        return lines[-1]

    return None


def _format_short_report_entry(report: Any) -> list[str]:
    when = getattr(report, "when", "")
    if when not in {"setup", "call", "teardown"}:
        return []

    if getattr(report, "passed", False) and when == "call":
        return [f"PASSED {report.nodeid}"]

    if getattr(report, "skipped", False):
        message = _extract_report_message(report)
        lines = [f"SKIPPED {report.nodeid}"]
        if message:
            lines.append(f"  reason: {message}")
        return lines

    if getattr(report, "failed", False):
        status = "FAILED" if when == "call" else "ERROR"
        message = _extract_report_message(report)
        lines = [f"{status} {report.nodeid}"]
        if message:
            lines.append(f"  message: {message}")
        return lines

    return []


def _configure_test_logging() -> None:
    logger = logging.getLogger("qsea")
    logger.setLevel(logging.DEBUG)
    if _has_file_handler(logger, DETAILED_TEST_LOG_PATH):
        return

    LOGS_DIR.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(DETAILED_TEST_LOG_PATH, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s\tLineNo:%(lineno)s\t%(funcName)s()\t%(levelname)s: %(message)s"
        )
    )
    logger.addHandler(file_handler)


_configure_test_logging()


def pytest_sessionstart(session: pytest.Session) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    with SHORT_TEST_LOG_PATH.open("w", encoding="utf-8") as log_file:
        log_file.write("TEST SESSION STARTED\n")


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    for line in _format_short_report_entry(report):
        _write_short_test_log(line)


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    parts = []
    for status in ("passed", "failed", "error", "skipped", "xfailed", "xpassed"):
        count = len(terminalreporter.stats.get(status, []))
        if count:
            parts.append(f"{status}={count}")

    summary = "TEST SUMMARY"
    if parts:
        summary = f"{summary} {' '.join(parts)}"
    _write_short_test_log(summary)
    _write_short_test_log(f"TEST SESSION FINISHED exitstatus={exitstatus}")


@pytest.fixture(scope="session")
def connection_config():
    api_key = os.environ.get("QLIKSENSE_API_KEY")
    if not api_key:
        pytest.skip("QLIKSENSE_API_KEY is required for integration tests.")

    return {"Authorization": api_key}


@pytest.fixture(scope="session")
def connection(connection_config):
    qsea.config.logQueryMaxLength = 10000
    conn = qsea.Connection(connection_config, QLIK_URL, timeout=60, verify_ssl=False)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def connection_factory(connection_config):
    def _make(timeout: int = 60):
        return qsea.Connection(connection_config, QLIK_URL, timeout=timeout, verify_ssl=False)

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
def clear_selections_after_test(request):
    yield
    marker = request.node.get_closest_marker("integration")
    if marker is None:
        return
    app_factory = request.getfixturevalue("app_factory")
    try:
        app = app_factory(load=False)
        app.clear_selections()
    except Exception:
        pass
