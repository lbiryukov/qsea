from __future__ import annotations

import pytest

import qsea

from ._integration_helpers import MAIN_APP_NAME, register_child_cleanup


def test_build_set_modifier_formats_supported_values():
    assert qsea._build_set_modifier({"Year": 2025}) == "{<[Year]={2025}>}"
    assert qsea._build_set_modifier({"City": "Moscow"}) == "{<[City]={'Moscow'}>}"
    assert qsea._build_set_modifier({"Year": [2024, 2025]}) == "{<[Year]={2024,2025}>}"

    result = qsea._build_set_modifier({"Year": 2025, "Month": 2})
    assert "[Year]={2025}" in result
    assert "[Month]={2}" in result
    assert result.startswith("{<")
    assert result.endswith(">}")
    assert qsea._build_set_modifier({}) == ""


@pytest.mark.integration
def test_evaluate_raw_expression_without_filters(app_factory):
    app = app_factory()
    result = app.evaluate("sum(1)")
    assert result["is_numeric"] is True
    assert result["value"] is not None


@pytest.mark.integration
def test_evaluate_master_measure_by_name_without_filters(app_factory, name_factory, cleanup_registry):
    measure_name = name_factory("EvalTestMs")
    app = app_factory()

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "measures", measure_name)

    assert app.measures.add(measure_name, definition="sum(1)") is True
    app.save()
    app = app_factory()

    result = app.evaluate(measure_name)
    assert result["is_numeric"] is True
    assert result["value"] is not None


@pytest.mark.integration
def test_evaluate_with_filters_via_hypercube(app_factory):
    app = app_factory()
    test_field = list(app.fields.children.keys())[0]

    result = app.evaluate("sum(1)", filters={test_field: 1}, method="evaluate")
    assert result["value"] is not None


@pytest.mark.integration
def test_evaluate_master_measure_with_filters_via_hypercube(app_factory, name_factory, cleanup_registry):
    measure_name = name_factory("EvalTestMsFiltered")
    app = app_factory()

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "measures", measure_name)

    assert app.measures.add(measure_name, definition="sum(1)") is True
    test_field = list(app.fields.children.keys())[0]

    result = app.evaluate(measure_name, filters={test_field: 1}, method="evaluate")
    assert result["value"] is not None


@pytest.mark.integration
def test_evaluate_with_filters_via_selections(app_factory):
    app = app_factory()
    test_field = list(app.fields.children.keys())[0]

    result = app.evaluate("sum(1)", filters={test_field: 1}, method="selections")
    assert result["value"] is not None


@pytest.mark.integration
def test_select_values_and_clear_selections_round_trip(app_factory):
    app = app_factory()
    test_field = list(app.fields.children.keys())[0]

    assert app.select_values(test_field, [1]) is True
    selected_result = app.evaluate("sum(1)")
    assert selected_result["value"] is not None

    assert app.clear_selections() is True
    cleared_result = app.evaluate("sum(1)")
    assert cleared_result["value"] is not None


@pytest.mark.integration
def test_evaluate_invalid_method_raises_value_error(app_factory):
    app = app_factory()

    with pytest.raises(ValueError):
        app.evaluate("sum(1)", method="invalid")


@pytest.mark.integration
def test_evaluate_unknown_field_in_selection_mode_raises_value_error(app_factory):
    app = app_factory()

    with pytest.raises(ValueError):
        app.evaluate("sum(1)", filters={"NonExistentField_XYZ_12345": 1}, method="selections")
