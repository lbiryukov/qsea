from __future__ import annotations

import pytest

from ._integration_helpers import RATING_OBJECT_ID, RATING_SHEET_NAME


pytestmark = [pytest.mark.integration, pytest.mark.experimental]


def test_object_dimension_update_persists(app_factory, name_factory, cleanup_registry):
    definition = name_factory("NewDimDefUpd")
    label = name_factory("lblUpd")
    calc_condition = name_factory("calcCondUpd")
    app = app_factory()
    sheet = app.sheets[RATING_SHEET_NAME]
    sheet.load()
    obj = sheet.objects[RATING_OBJECT_ID]
    obj.load()

    dimension_id = obj.dimensions[0].id
    original_dimension = obj.dimensions[dimension_id]
    original_definition = list(original_dimension.definition)
    original_label = list(original_dimension.label)
    original_calc_condition = original_dimension.calc_condition

    def _cleanup() -> None:
        restore_app = app_factory()
        restore_sheet = restore_app.sheets[RATING_SHEET_NAME]
        restore_sheet.load()
        restore_obj = restore_sheet.objects[RATING_OBJECT_ID]
        restore_obj.load()
        restore_obj.dimensions[dimension_id].update(
            definition=original_definition[0],
            label=original_label[0],
            calc_condition=original_calc_condition,
        )
        restore_app.save()

    cleanup_registry.append(_cleanup)

    assert obj.dimensions[dimension_id].update(
        definition=definition,
        label=label,
        calc_condition=calc_condition,
    ) is True
    assert obj.dimensions[dimension_id].definition == [definition]
    assert obj.dimensions[dimension_id].label == [label]
    assert obj.dimensions[dimension_id].calc_condition == calc_condition

    app.save()
    app = app_factory()
    sheet = app.sheets[RATING_SHEET_NAME]
    sheet.load()
    obj = sheet.objects[RATING_OBJECT_ID]
    obj.load()

    assert obj.dimensions[dimension_id].definition == [definition]
    assert obj.dimensions[dimension_id].label == [label]
    assert obj.dimensions[dimension_id].calc_condition == calc_condition


def test_object_measure_update_persists(app_factory, name_factory, cleanup_registry):
    definition = name_factory("NewMeasDefUpd")
    label = name_factory("lblUpd")
    label_expression = name_factory("lblExprUpd")
    calc_condition = name_factory("calcCondUpd")
    app = app_factory()
    sheet = app.sheets[RATING_SHEET_NAME]
    sheet.load()
    obj = sheet.objects[RATING_OBJECT_ID]
    obj.load()

    measure_id = obj.measures[0].id
    original_measure = obj.measures[measure_id]
    original_definition = original_measure.definition
    original_label = original_measure.label
    original_label_expression = original_measure.label_expression
    original_calc_condition = original_measure.calc_condition

    def _cleanup() -> None:
        restore_app = app_factory()
        restore_sheet = restore_app.sheets[RATING_SHEET_NAME]
        restore_sheet.load()
        restore_obj = restore_sheet.objects[RATING_OBJECT_ID]
        restore_obj.load()
        restore_obj.measures[measure_id].update(
            definition=original_definition,
            label=original_label,
            label_expression=original_label_expression,
            calc_condition=original_calc_condition,
        )
        restore_app.save()

    cleanup_registry.append(_cleanup)

    assert obj.measures[measure_id].update(
        definition=definition,
        label=label,
        label_expression=label_expression,
        calc_condition=calc_condition,
    ) is True
    assert obj.measures[measure_id].definition == definition
    assert obj.measures[measure_id].label == label
    assert obj.measures[measure_id].label_expression == label_expression
    assert obj.measures[measure_id].calc_condition == calc_condition

    app.save()
    app = app_factory()
    sheet = app.sheets[RATING_SHEET_NAME]
    sheet.load()
    obj = sheet.objects[RATING_OBJECT_ID]
    obj.load()

    assert obj.measures[measure_id].definition == definition
    assert obj.measures[measure_id].label == label
    assert obj.measures[measure_id].label_expression == label_expression
    assert obj.measures[measure_id].calc_condition == calc_condition
