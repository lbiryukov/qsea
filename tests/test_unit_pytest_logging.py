from __future__ import annotations

from types import SimpleNamespace

from tests import conftest as test_conftest


def test_format_short_report_entry_for_passed_test():
    report = SimpleNamespace(
        when="call",
        passed=True,
        failed=False,
        skipped=False,
        nodeid="tests/test_sample.py::test_ok",
        longrepr=None,
        longreprtext="",
    )

    assert test_conftest._format_short_report_entry(report) == [
        "PASSED tests/test_sample.py::test_ok"
    ]


def test_format_short_report_entry_for_failed_test_uses_last_error_line():
    report = SimpleNamespace(
        when="call",
        passed=False,
        failed=True,
        skipped=False,
        nodeid="tests/test_sample.py::test_fail",
        longrepr=None,
        longreprtext="AssertionError: boom\nE assert 1 == 2",
    )

    assert test_conftest._format_short_report_entry(report) == [
        "FAILED tests/test_sample.py::test_fail",
        "  message: E assert 1 == 2",
    ]


def test_format_short_report_entry_marks_setup_failure_as_error():
    report = SimpleNamespace(
        when="setup",
        passed=False,
        failed=True,
        skipped=False,
        nodeid="tests/test_sample.py::test_error",
        longrepr=None,
        longreprtext="RuntimeError: setup exploded",
    )

    assert test_conftest._format_short_report_entry(report) == [
        "ERROR tests/test_sample.py::test_error",
        "  message: RuntimeError: setup exploded",
    ]


def test_session_hooks_write_short_log(tmp_path, monkeypatch):
    monkeypatch.setattr(test_conftest, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(test_conftest, "SHORT_TEST_LOG_PATH", tmp_path / "qsea_pytest_short.log")

    terminal_reporter = SimpleNamespace(stats={"passed": [object(), object()], "failed": [object()]})
    report = SimpleNamespace(
        when="call",
        passed=True,
        failed=False,
        skipped=False,
        nodeid="tests/test_sample.py::test_ok",
        longrepr=None,
        longreprtext="",
    )

    test_conftest.pytest_sessionstart(SimpleNamespace())
    test_conftest.pytest_runtest_logreport(report)
    test_conftest.pytest_terminal_summary(terminal_reporter, 1, SimpleNamespace())

    content = test_conftest.SHORT_TEST_LOG_PATH.read_text(encoding="utf-8").splitlines()
    assert content == [
        "TEST SESSION STARTED",
        "PASSED tests/test_sample.py::test_ok",
        "TEST SUMMARY passed=2 failed=1",
        "TEST SESSION FINISHED exitstatus=1",
    ]
