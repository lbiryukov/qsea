"""Unit tests for query() and _open_connection() with mocked WebSocket.

These tests do NOT require a live Qlik Sense connection.
"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch, call

import pytest

import qsea


class _FakeWS:
    """Minimal stand-in for a websocket.WebSocket."""

    def __init__(self, responses: list[str | dict]):
        self._responses = [json.dumps(r) if isinstance(r, dict) else r for r in responses]
        self._idx = 0
        self.sent: list[str] = []
        self.connected = True

    def send(self, data: str):
        self.sent.append(data)

    def recv(self) -> str:
        if self._idx >= len(self._responses):
            raise ConnectionError("no more responses")
        resp = self._responses[self._idx]
        self._idx += 1
        return resp

    def close(self):
        self.connected = False


# ---------------------------------------------------------------------------
# query()
# ---------------------------------------------------------------------------

class TestQueryBasic:
    def test_returns_result_on_success(self):
        ws = _FakeWS([{"jsonrpc": "2.0", "id": 1, "result": {"qReturn": 42}}])
        result = qsea.query(ws, {"jsonrpc": "2.0", "id": 1, "method": "Foo", "handle": 1, "params": []})
        assert result is not None
        assert result["result"]["qReturn"] == 42

    def test_sends_json_to_websocket(self):
        ws = _FakeWS([{"jsonrpc": "2.0", "id": 1, "result": {}}])
        payload = {"jsonrpc": "2.0", "id": 1, "method": "Bar", "handle": 1, "params": []}
        qsea.query(ws, payload)
        assert json.loads(ws.sent[0]) == payload


class TestQueryPushNotificationSkipping:
    def test_skips_push_notifications_without_id(self):
        ws = _FakeWS([
            {"params": {"qSessionState": "SESSION_ATTACHED"}},
            {"params": {"change": [1]}},
            {"jsonrpc": "2.0", "id": 1, "result": {"qReturn": "ok"}},
        ])
        result = qsea.query(ws, {"jsonrpc": "2.0", "id": 1, "method": "Foo", "handle": 1, "params": []})
        assert result is not None
        assert result["result"]["qReturn"] == "ok"

    def test_aborts_after_max_skipped_notifications(self):
        notifications = [{"params": {"change": [i]}} for i in range(51)]
        ws = _FakeWS(notifications)
        result = qsea.query(ws, {"jsonrpc": "2.0", "id": 1, "method": "Foo", "handle": 1, "params": []})
        assert result is None

    def test_exact_max_skipped_boundary(self):
        notifications = [{"params": {"change": [i]}} for i in range(50)]
        notifications.append({"jsonrpc": "2.0", "id": 1, "result": {"qReturn": "last"}})
        ws = _FakeWS(notifications)
        result = qsea.query(ws, {"jsonrpc": "2.0", "id": 1, "method": "Foo", "handle": 1, "params": []})
        assert result is None


class TestQueryRetryAttempts:
    def test_returns_none_on_exception_with_single_attempt(self):
        ws = _FakeWS([])
        result = qsea.query(ws, {"jsonrpc": "2.0", "id": 1, "method": "Foo", "handle": 1, "params": []}, attempts=1)
        assert result is None

    def test_retries_up_to_attempts_count(self):
        ws = MagicMock()
        ws.send = MagicMock()
        ws.recv = MagicMock(side_effect=[
            ConnectionError("fail1"),
            ConnectionError("fail2"),
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}),
        ])
        result = qsea.query(ws, {"jsonrpc": "2.0", "id": 1, "method": "Foo", "handle": 1, "params": []}, attempts=3)
        assert result is not None
        assert result["result"]["ok"] is True
        assert ws.recv.call_count == 3

    def test_exhausts_all_attempts_then_returns_none(self):
        ws = MagicMock()
        ws.send = MagicMock()
        ws.recv = MagicMock(side_effect=ConnectionError("fail"))
        result = qsea.query(ws, {"jsonrpc": "2.0", "id": 1, "method": "Foo", "handle": 1, "params": []}, attempts=3)
        assert result is None
        assert ws.recv.call_count == 3


class TestQueryErrorHandling:
    def test_returns_error_dict_when_engine_returns_error(self):
        ws = _FakeWS([{"jsonrpc": "2.0", "id": 1, "error": {"code": 500, "message": "boom"}}])
        result = qsea.query(ws, {"jsonrpc": "2.0", "id": 1, "method": "Foo", "handle": 1, "params": []})
        assert result is not None
        assert "error" in result
        assert result["error"]["code"] == 500

    def test_qvalue_is_remapped_to_qreturn(self):
        ws = _FakeWS([{"jsonrpc": "2.0", "id": 1, "result": {"qValue": 99}}])
        result = qsea.query(ws, {"jsonrpc": "2.0", "id": 1, "method": "Foo", "handle": 1, "params": []})
        assert result["result"]["qReturn"] == 99
        assert result["result"]["qValue"] == 99


# ---------------------------------------------------------------------------
# _open_connection()
# ---------------------------------------------------------------------------

class TestOpenConnectionSuccess:
    @patch("qsea._engine.websocket.create_connection")
    def test_returns_ws_on_session_created(self, mock_create):
        mock_ws = MagicMock()
        mock_ws.recv = MagicMock(side_effect=[
            json.dumps({"params": {"qSessionState": "noop"}}),
            json.dumps({"params": {"qSessionState": "SESSION_CREATED"}}),
        ])
        mock_create.return_value = mock_ws

        ws = qsea._open_connection("wss://test/app/", {}, timeout=5)
        assert ws is mock_ws

    @patch("qsea._engine.websocket.create_connection")
    def test_returns_ws_on_session_attached(self, mock_create):
        mock_ws = MagicMock()
        mock_ws.recv = MagicMock(side_effect=[
            json.dumps({"params": {"other": "data"}}),
            json.dumps({"params": {"qSessionState": "SESSION_ATTACHED"}}),
        ])
        mock_create.return_value = mock_ws

        ws = qsea._open_connection("wss://test/app/", {}, timeout=5)
        assert ws is mock_ws


class TestOpenConnectionRetryOnMaxSessions:
    @patch("qsea._engine.websocket.create_connection")
    def test_retries_on_max_parallel_sessions(self, mock_create):
        fatal_ws = MagicMock()
        fatal_ws.recv = MagicMock(return_value=json.dumps({
            "params": {"severity": "fatal", "message": "MaxParallelSessionsExceeded"}
        }))
        fatal_ws.close = MagicMock()

        ok_ws = MagicMock()
        ok_ws.recv = MagicMock(side_effect=[
            json.dumps({"params": {"something": True}}),
            json.dumps({"params": {"qSessionState": "SESSION_CREATED"}}),
        ])

        mock_create.side_effect = [fatal_ws, ok_ws]

        with patch("time.sleep"):
            ws = qsea._open_connection("wss://test/app/", {}, timeout=5,
                                       max_retries=2, retry_delay=0.01)
        assert ws is ok_ws
        fatal_ws.close.assert_called_once()

    @patch("qsea._engine.websocket.create_connection")
    def test_raises_after_all_retries_exhausted(self, mock_create):
        fatal_ws = MagicMock()
        fatal_ws.recv = MagicMock(return_value=json.dumps({
            "params": {"severity": "fatal", "message": "MaxParallelSessionsExceeded"}
        }))
        fatal_ws.close = MagicMock()
        mock_create.return_value = fatal_ws

        with patch("time.sleep"):
            with pytest.raises(ConnectionError, match="MaxParallelSessionsExceeded"):
                qsea._open_connection("wss://test/app/", {}, timeout=5,
                                      max_retries=3, retry_delay=0.01)
        assert fatal_ws.close.call_count == 3


class TestOpenConnectionFatalError:
    @patch("qsea._engine.websocket.create_connection")
    def test_non_retryable_fatal_raises_immediately(self, mock_create):
        fatal_ws = MagicMock()
        fatal_ws.recv = MagicMock(return_value=json.dumps({
            "params": {"severity": "fatal", "message": "LicenseExpired"}
        }))
        fatal_ws.close = MagicMock()
        mock_create.return_value = fatal_ws

        with pytest.raises(ConnectionError, match="LicenseExpired"):
            qsea._open_connection("wss://test/app/", {}, timeout=5,
                                  max_retries=3, retry_delay=0.01)
        assert mock_create.call_count == 1
        fatal_ws.close.assert_called_once()


class TestOpenConnectionSSL:
    @patch("qsea._engine.websocket.create_connection")
    def test_verify_ssl_true_sends_empty_sslopt(self, mock_create):
        mock_ws = MagicMock()
        mock_ws.recv = MagicMock(side_effect=[
            json.dumps({"params": {}}),
            json.dumps({"params": {"qSessionState": "SESSION_CREATED"}}),
        ])
        mock_create.return_value = mock_ws

        qsea._open_connection("wss://test/app/", {}, timeout=5, verify_ssl=True)
        _, kwargs = mock_create.call_args
        assert kwargs.get("sslopt", {}) == {}

    @patch("qsea._engine.websocket.create_connection")
    def test_verify_ssl_false_sends_cert_none(self, mock_create):
        import ssl
        mock_ws = MagicMock()
        mock_ws.recv = MagicMock(side_effect=[
            json.dumps({"params": {}}),
            json.dumps({"params": {"qSessionState": "SESSION_CREATED"}}),
        ])
        mock_create.return_value = mock_ws

        qsea._open_connection("wss://test/app/", {}, timeout=5, verify_ssl=False)
        _, kwargs = mock_create.call_args
        assert kwargs["sslopt"]["cert_reqs"] == ssl.CERT_NONE


class TestOpenConnectionUnexpectedState:
    @patch("qsea._engine.websocket.create_connection")
    def test_returns_ws_on_unexpected_session_state(self, mock_create):
        mock_ws = MagicMock()
        mock_ws.recv = MagicMock(side_effect=[
            json.dumps({"params": {"info": "something"}}),
            json.dumps({"params": {"qSessionState": "UNKNOWN_STATE"}}),
        ])
        mock_create.return_value = mock_ws

        ws = qsea._open_connection("wss://test/app/", {}, timeout=5)
        assert ws is mock_ws


class TestOpenConnectionNonFatalSeverity:
    @patch("qsea._engine.websocket.create_connection")
    def test_continues_on_non_fatal_severity(self, mock_create):
        warn_ws = MagicMock()
        warn_ws.recv = MagicMock(return_value=json.dumps({
            "params": {"severity": "warning", "message": "SomeWarning"}
        }))

        ok_ws = MagicMock()
        ok_ws.recv = MagicMock(side_effect=[
            json.dumps({"params": {}}),
            json.dumps({"params": {"qSessionState": "SESSION_CREATED"}}),
        ])

        mock_create.side_effect = [warn_ws, ok_ws]

        ws = qsea._open_connection("wss://test/app/", {}, timeout=5, max_retries=2)
        assert ws is ok_ws
