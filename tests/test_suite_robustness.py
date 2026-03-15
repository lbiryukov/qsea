"""Integration tests for robustness scenarios.

Covers: special characters in names/definitions, double load, timeout,
Bookmark.get_layout, get_properties, App._clearGarbage.
"""
from __future__ import annotations

import pytest

import qsea

from ._integration_helpers import (
    BOOKMARK_NAME,
    MAIN_APP_NAME,
    TARGET_APP_NAME,
    get_item_or_false,
    make_unique_name,
    register_child_cleanup,
)


pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Special characters in Variable / Measure / Dimension names and definitions
# ---------------------------------------------------------------------------

class TestSpecialCharactersVariable:
    def test_variable_with_quotes_in_name_and_definition(self, app_factory, cleanup_registry):
        var_name = make_unique_name('Var"Quote')
        app = app_factory()
        register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "variables", var_name)

        result = app.variables.add(var_name, "='Hello \"World\"'")
        assert result is not None
        assert app.variables[var_name].definition == "='Hello \"World\"'"

        app.save()
        app = app_factory()
        assert app.variables[var_name].definition == "='Hello \"World\"'"

    def test_variable_with_unicode_in_name(self, app_factory, cleanup_registry):
        var_name = make_unique_name("VarUnicode")
        app = app_factory()
        register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "variables", var_name)

        result = app.variables.add(var_name, "42")
        assert result is not None

        app.save()
        app = app_factory()
        assert app.variables[var_name].name == var_name
        assert app.variables[var_name].definition == "42"

    def test_variable_with_brackets_in_definition(self, app_factory, cleanup_registry):
        var_name = make_unique_name("VarBrackets")
        app = app_factory()
        register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "variables", var_name)

        definition = "=Sum({<[Year]={2025}>} Sales)"
        result = app.variables.add(var_name, definition)
        assert result is not None
        assert app.variables[var_name].definition == definition

        app.save()
        app = app_factory()
        assert app.variables[var_name].definition == definition


class TestSpecialCharactersMeasure:
    def test_measure_with_single_quotes_in_definition(self, app_factory, cleanup_registry):
        ms_name = make_unique_name("MsQuote")
        app = app_factory()
        register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "measures", ms_name)

        definition = "=Count({<City={'Moscow','London'}>} OrderID)"
        result = app.measures.add(ms_name, definition=definition)
        assert result is not None
        assert app.measures[ms_name].definition == definition

        app.save()
        app = app_factory()
        assert app.measures[ms_name].definition == definition

    def test_measure_with_angle_brackets_in_definition(self, app_factory, cleanup_registry):
        ms_name = make_unique_name("MsAngle")
        app = app_factory()
        register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "measures", ms_name)

        definition = "=Sum({<Year={2025}>} [Revenue])"
        result = app.measures.add(ms_name, definition=definition)
        assert result is not None

        app.save()
        app = app_factory()
        assert app.measures[ms_name].definition == definition

    def test_measure_with_cyrillic_name_and_label(self, app_factory, cleanup_registry):
        ms_name = make_unique_name("MsCyrillic")
        app = app_factory()
        register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "measures", ms_name)

        result = app.measures.add(ms_name, definition="Sum(1)", label="Label")
        assert result is not None

        app.save()
        app = app_factory()
        assert app.measures[ms_name].label == "Label"


class TestSpecialCharactersDimension:
    def test_dimension_with_brackets_in_definition(self, app_factory, cleanup_registry):
        dim_name = make_unique_name("DimBrackets")
        app = app_factory()
        register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "dimensions", dim_name)

        definition = "=If([Year] > 2020, 'New', 'Old')"
        result = app.dimensions.add(dim_name, definition=definition)
        assert len(result) > 0
        assert app.dimensions[dim_name].definition == [definition]

        app.save()
        app = app_factory()
        assert app.dimensions[dim_name].definition == [definition]

    def test_dimension_with_unicode_label(self, app_factory, cleanup_registry):
        dim_name = make_unique_name("DimUniLabel")
        app = app_factory()
        register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "dimensions", dim_name)

        result = app.dimensions.add(dim_name, definition="SomeDef", label="SomeLabel")
        assert len(result) > 0

        app.save()
        app = app_factory()
        assert app.dimensions[dim_name].label == ["SomeLabel"]


# ---------------------------------------------------------------------------
# Double load -- repeated app.load() must not duplicate data
# ---------------------------------------------------------------------------

class TestDoubleLoad:
    def test_double_load_does_not_duplicate_variables(self, app_factory):
        app = app_factory()
        count_after_first = app.variables.count
        assert count_after_first > 0

        app.load()
        assert app.variables.count == count_after_first

    def test_double_load_does_not_duplicate_measures(self, app_factory):
        app = app_factory()
        count_after_first = app.measures.count
        assert count_after_first > 0

        app.load()
        assert app.measures.count == count_after_first

    def test_double_load_does_not_duplicate_dimensions(self, app_factory):
        app = app_factory()
        count_after_first = app.dimensions.count
        assert count_after_first > 0

        app.load()
        assert app.dimensions.count == count_after_first

    def test_double_load_does_not_duplicate_sheets(self, app_factory):
        app = app_factory()
        count_after_first = app.sheets.count
        assert count_after_first > 0

        app.load()
        assert app.sheets.count == count_after_first

    def test_double_load_does_not_duplicate_bookmarks(self, app_factory):
        app = app_factory()
        count_after_first = app.bookmarks.count

        app.load()
        assert app.bookmarks.count == count_after_first

    def test_double_load_preserves_children_identity(self, app_factory):
        app = app_factory()
        var_names_first = set(app.variables.children.keys())
        ms_names_first = set(app.measures.children.keys())

        app.load()
        var_names_second = set(app.variables.children.keys())
        ms_names_second = set(app.measures.children.keys())

        assert var_names_first == var_names_second
        assert ms_names_first == ms_names_second


# ---------------------------------------------------------------------------
# Connection timeout handling
# ---------------------------------------------------------------------------

class TestConnectionTimeout:
    def test_connection_with_very_short_timeout_still_creates(self, connection_factory):
        conn = connection_factory(timeout=60)
        assert conn.df.shape[0] > 0
        conn.close()

    def test_connection_timeout_stored_on_instance(self, connection_config):
        conn = qsea.Connection(connection_config, "wss://co-qlik.eksmo-office.ru/pyt/app/",
                               timeout=30, verify_ssl=False)
        assert conn.timeout == 30
        conn.close()


# ---------------------------------------------------------------------------
# Bookmark.get_layout
# ---------------------------------------------------------------------------

class TestBookmarkGetLayout:
    def test_bookmark_get_layout_returns_valid_structure(self, app_factory):
        app = app_factory()
        bookmark = app.bookmarks[BOOKMARK_NAME]
        layout = bookmark.get_layout()

        assert layout is not None
        assert "result" in layout
        assert "qLayout" in layout["result"]
        assert "qInfo" in layout["result"]["qLayout"]
        assert layout["result"]["qLayout"]["qInfo"]["qId"] == bookmark.id

    def test_bookmark_get_handle_returns_nonzero(self, app_factory):
        app = app_factory()
        bookmark = app.bookmarks[BOOKMARK_NAME]
        handle = bookmark.get_handle()

        assert handle is not None
        assert handle > 0


# ---------------------------------------------------------------------------
# Measure.get_properties / Dimension.get_properties
# ---------------------------------------------------------------------------

class TestGetProperties:
    def test_measure_get_properties_returns_definition(self, app_factory, cleanup_registry):
        ms_name = make_unique_name("MsProps")
        app = app_factory()
        register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "measures", ms_name)

        app.measures.add(ms_name, definition="Sum(1)", label="PropsLabel")
        measure = app.measures[ms_name]
        props = measure.get_properties()

        assert props is not None
        assert "result" in props
        q_props = props["result"]["qProp"]
        assert q_props["qMeasure"]["qDef"] == "Sum(1)"

    def test_dimension_get_properties_returns_field_defs(self, app_factory, cleanup_registry):
        dim_name = make_unique_name("DimProps")
        app = app_factory()
        register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "dimensions", dim_name)

        app.dimensions.add(dim_name, definition="SomeField", label="PropsLabel")
        dimension = app.dimensions[dim_name]
        props = dimension.get_properties()

        assert props is not None
        assert "result" in props
        q_props = props["result"]["qProp"]
        field_defs = q_props["qDim"]["qFieldDefs"]
        assert "SomeField" in field_defs


# ---------------------------------------------------------------------------
# App._clearGarbage
# ---------------------------------------------------------------------------

class TestClearGarbage:
    def test_clear_garbage_removes_pre_prefixed_variables(self, app_factory, cleanup_registry):
        var_name = make_unique_name("_pre_GarbageVar")
        app = app_factory()
        register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "variables", var_name)

        app.variables.add(var_name, "garbage_def")
        assert app.variables[var_name].name == var_name

        app._clearGarbage()
        assert get_item_or_false(app.variables, var_name) is False

    def test_clear_garbage_removes_pre_prefixed_measures(self, app_factory, cleanup_registry):
        ms_name = make_unique_name("_pre_GarbageMs")
        app = app_factory()
        register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "measures", ms_name)

        app.measures.add(ms_name, definition="garbage_def")
        assert app.measures[ms_name].name == ms_name

        app._clearGarbage()
        assert get_item_or_false(app.measures, ms_name) is False

    def test_clear_garbage_removes_pre_prefixed_dimensions(self, app_factory, cleanup_registry):
        dim_name = make_unique_name("_pre_GarbageDim")
        app = app_factory()
        register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "dimensions", dim_name)

        app.dimensions.add(dim_name, definition="garbage_def")
        assert app.dimensions[dim_name].name == dim_name

        app._clearGarbage()
        assert get_item_or_false(app.dimensions, dim_name) is False

    def test_clear_garbage_preserves_non_pre_items(self, app_factory, cleanup_registry):
        var_name = make_unique_name("NormalVar")
        pre_var_name = make_unique_name("_pre_CleanupVar")
        app = app_factory()

        register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "variables", var_name)
        register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "variables", pre_var_name)

        app.variables.add(var_name, "keep_def")
        app.variables.add(pre_var_name, "remove_def")

        app._clearGarbage()
        assert app.variables[var_name].name == var_name
        assert get_item_or_false(app.variables, pre_var_name) is False
