from __future__ import annotations

import pytest

import qsea

from ._integration_helpers import (
    BOOKMARK_NAME,
    COPY_OBJECT_SOURCE_ID,
    EXPORT_OBJECT_ID,
    FILTER_OBJECT_ID,
    FORMATS_OBJECT_ID,
    FORMATS_SHEET_NAME,
    MAIN_APP_NAME,
    RATING_OBJECT_ID,
    RATING_SHEET_NAME,
    TARGET_APP_NAME,
    VISUALS_SHEET_NAME,
    register_child_cleanup,
)


pytestmark = [pytest.mark.integration]


def test_package_smoke_check():
    assert qsea._test() == 39


def test_connection_tracks_main_and_secondary_apps(connection_factory):
    connection = connection_factory()
    assert connection.df.shape[0] > 0
    assert connection.main_app_id is None
    assert len(connection.wss) == 0

    app1 = qsea.App(connection, MAIN_APP_NAME)
    app1.variables.load()
    assert app1.variables.df.shape[0] > 0
    assert connection.main_app_id is not None

    app2 = qsea.App(connection, TARGET_APP_NAME)
    app2.variables.load()
    assert app2.variables.df.shape[0] > 0
    assert connection.main_app_id != app2.id
    assert app2.id in connection.wss


def test_app_load_populates_collections(app_factory):
    app = app_factory()
    assert app.variables.count > 0
    assert app.measures.count > 0
    assert app.dimensions.count > 0
    assert app.fields.count > 0
    assert app.sheets.count > 0
    assert app.bookmarks.count >= 0


def test_app_load_depth_2_loads_sheet_objects(app_factory):
    app = app_factory(depth=2)
    sheet = app.sheets[RATING_SHEET_NAME]
    assert sheet.objects.df.shape[0] > 0


def test_app_load_depth_3_loads_object_dimensions_and_measures(app_factory):
    app = app_factory(depth=3)
    sheet = app.sheets[RATING_SHEET_NAME]
    obj = sheet.objects[RATING_OBJECT_ID]
    assert obj.dimensions.df.shape[0] > 0
    assert obj.measures.df.shape[0] > 0


def test_sheet_objects_dataframe_loads(app_factory):
    app = app_factory()
    sheet = app.sheets[RATING_SHEET_NAME]
    sheet.load()
    sheet.objects.load()
    assert sheet.objects.df.shape[0] > 0


def test_object_measure_library_id_update_persists(app_factory, cleanup_registry):
    app = app_factory()
    sheet = app.sheets[FORMATS_SHEET_NAME]
    sheet.load()
    obj = sheet.objects[FORMATS_OBJECT_ID]
    obj.load()
    measure = obj.measures["LZvVVLb"]
    original_library_id = measure.library_id
    new_library_id = "zCPGZr" if original_library_id == "RJHx" else "RJHx"

    def _cleanup() -> None:
        restore_app = app_factory()
        restore_sheet = restore_app.sheets[FORMATS_SHEET_NAME]
        restore_sheet.load()
        restore_obj = restore_sheet.objects[FORMATS_OBJECT_ID]
        restore_obj.load()
        restore_obj.measures["LZvVVLb"].update(library_id=original_library_id)
        restore_app.save()

    cleanup_registry.append(_cleanup)

    assert measure.update(library_id=new_library_id) is True
    assert measure.library_id == new_library_id

    app.save()
    app = app_factory()
    sheet = app.sheets[FORMATS_SHEET_NAME]
    sheet.load()
    obj = sheet.objects[FORMATS_OBJECT_ID]
    obj.load()

    assert obj.measures["LZvVVLb"].library_id == new_library_id


@pytest.mark.slow
def test_multiple_apps_can_be_loaded_over_single_connection(connection):
    app1 = qsea.App(connection, "План-факт продаж(6)")
    app1.load(3)
    assert app1.sheets.count >= 0

    app2 = qsea.App(connection, "Дашборд(1)")
    app2.load(3)
    assert app2.sheets.count >= 0

    app3 = qsea.App(connection, "ETL_0202_Transform_Факт SMART2(4)")
    app3.load(3)
    assert app3.sheets.count >= 0

    app4 = qsea.App(connection, "Продажи, ROI, остатки(3)")
    app4.load(3)
    assert app4.sheets.count >= 0


def test_object_export_data_returns_file_for_chart(app_factory):
    app = app_factory()
    sheet = app.sheets[VISUALS_SHEET_NAME]
    sheet.load()

    assert sheet.objects[EXPORT_OBJECT_ID].export_data("xlsx") is not None
    assert sheet.objects[EXPORT_OBJECT_ID].export_data("csv") is not None


def test_object_export_data_returns_none_for_filter(app_factory):
    app = app_factory()
    sheet = app.sheets[VISUALS_SHEET_NAME]
    sheet.load()

    assert sheet.objects[FILTER_OBJECT_ID].export_data("csv") is None


def test_get_layout_works_for_master_items_sheet_object_and_bookmark(app_factory, name_factory, cleanup_registry):
    measure_name = name_factory("NewMs123")
    dimension_name = name_factory("NewDim123")
    variable_name = name_factory("NewVar123")
    app = app_factory()

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "measures", measure_name)
    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "dimensions", dimension_name)
    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "variables", variable_name)

    assert app.measures.add(measure_name, "SomeDef") is True
    assert len(app.dimensions.add(dimension_name, "SomeDef")) > 0
    assert app.variables.add(variable_name, "SomeVar") is True

    measure_layout = app.measures[measure_name].get_layout()
    dimension_layout = app.dimensions[dimension_name].get_layout()
    variable_layout = app.variables[variable_name].get_layout()
    sheet_layout = app.sheets[VISUALS_SHEET_NAME].get_layout()

    sheet = app.sheets[VISUALS_SHEET_NAME]
    sheet.load()
    object_layout = sheet.objects[EXPORT_OBJECT_ID].get_layout()
    bookmark_layout = app.bookmarks[BOOKMARK_NAME].get_layout()

    assert measure_layout["result"]["qLayout"]["qMeta"]["title"] == measure_name
    assert dimension_layout["result"]["qLayout"]["qMeta"]["title"] == dimension_name
    assert variable_layout["result"]["qLayout"]["qText"] == "SomeVar"
    assert sheet_layout["result"]["qLayout"]["qMeta"]["title"] == VISUALS_SHEET_NAME
    assert object_layout["result"]["qLayout"]["qInfo"]["qId"] == EXPORT_OBJECT_ID
    assert bookmark_layout["result"]["qLayout"]["qInfo"]["qId"]


def test_bookmarks_collection_loaded(app_factory):
    app = app_factory()
    assert len(app.bookmarks.df) > 0
    assert len(app.bookmarks.df) == app.bookmarks.count
