"""Additional integration tests for previously uncovered functionality.

Covers: Connection.close, Connection.reload_app_list, App.save return value,
Sheet.delete, select_values toggle mode.
"""
from __future__ import annotations

import pytest

import qsea

from ._integration_helpers import (
    MAIN_APP_NAME,
    TARGET_APP_NAME,
    make_unique_name,
    register_sheet_cleanup,
)


pytestmark = [pytest.mark.integration]


def test_connection_close_shuts_down_websockets(connection_factory):
    conn = connection_factory()
    app = qsea.App(conn, TARGET_APP_NAME)
    ws = conn.wss[app.id]
    assert ws.connected is True
    assert len(conn.wss) == 1

    conn.close()
    assert ws.connected is False
    assert len(conn.wss) == 0


def test_connection_context_manager_closes_on_exit(connection_factory):
    with connection_factory() as conn:
        app = qsea.App(conn, TARGET_APP_NAME)
        ws = conn.wss[app.id]
        assert ws.connected is True

    assert ws.connected is False
    assert len(conn.wss) == 0


def test_connection_close_with_secondary_apps(connection_factory):
    conn = connection_factory()
    app = qsea.App(conn, TARGET_APP_NAME)
    ws = conn.wss[app.id]
    assert ws.connected is True
    assert len(conn.wss) == 1

    conn.close()
    assert ws.connected is False
    assert len(conn.wss) == 0


def test_connection_reload_app_list_updates_dataframe(connection):
    original_count = len(connection.df)
    connection.reload_app_list()
    assert len(connection.df) == original_count
    assert "qDocName" in connection.df.columns


def test_app_save_returns_true(app_factory, name_factory, cleanup_registry):
    var_name = name_factory("SaveTest")
    app = app_factory()

    from ._integration_helpers import register_child_cleanup
    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "variables", var_name)

    app.variables.add(var_name, "1")
    result = app.save()
    assert result is True


def test_sheet_delete_removes_from_app_and_engine(app_factory, cleanup_registry):
    sheet_name = make_unique_name("DelSheet")
    app = app_factory()

    register_sheet_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, sheet_name)

    app.sheets.add(name=sheet_name)
    app.save()
    app = app_factory()

    assert sheet_name in [sh.name for sh in app.sheets]
    sheet = app.sheets[sheet_name]
    result = sheet.delete()
    assert result is True
    app.save()

    app = app_factory()
    assert sheet_name not in [sh.name for sh in app.sheets]


def test_select_values_toggle_mode(app_factory):
    app = app_factory()
    test_field = list(app.fields.children.keys())[0]

    assert app.select_values(test_field, [1], toggle=True) is True
    assert app.clear_selections() is True
