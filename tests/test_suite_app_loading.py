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
    get_first_field_with_value,
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
    sheet = app.sheets[FORMATS_SHEET_NAME]
    obj = sheet.objects[FORMATS_OBJECT_ID]
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
    app1 = qsea.App(connection, MAIN_APP_NAME)
    app1.load(3)
    assert app1.sheets.count >= 0

    app2 = qsea.App(connection, TARGET_APP_NAME)
    app2.load(3)
    assert app2.sheets.count >= 0


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


def test_object_get_data_returns_dataframe_for_chart(app_factory):
    import pandas as pd
    app = app_factory()
    sheet = app.sheets[VISUALS_SHEET_NAME]
    sheet.load()

    df = sheet.objects[EXPORT_OBJECT_ID].get_data()
    assert df is not None
    assert isinstance(df, pd.DataFrame)
    assert len(df.columns) > 0
    assert len(df) > 0


def test_object_get_data_returns_none_for_filter(app_factory):
    app = app_factory()
    sheet = app.sheets[VISUALS_SHEET_NAME]
    sheet.load()

    assert sheet.objects[FILTER_OBJECT_ID].get_data() is None


def test_object_get_data_with_filters_returns_filtered_dataframe(app_factory):
    import pandas as pd
    app = app_factory()
    sheet = app.sheets[VISUALS_SHEET_NAME]
    sheet.load()

    obj = sheet.objects[EXPORT_OBJECT_ID]
    df_all = obj.get_data()
    assert df_all is not None and len(df_all) > 0

    test_field, test_value = get_first_field_with_value(app)
    assert test_field is not None, "No field with values found in test app"
    df_filtered = obj.get_data(filters={test_field: test_value})
    assert df_filtered is not None
    assert isinstance(df_filtered, pd.DataFrame)
    assert len(df_filtered) <= len(df_all)


def test_object_get_data_with_filters_clears_selections(app_factory):
    import pandas as pd
    app = app_factory()
    sheet = app.sheets[VISUALS_SHEET_NAME]
    sheet.load()

    obj = sheet.objects[EXPORT_OBJECT_ID]
    df_before = obj.get_data()

    test_field, test_value = get_first_field_with_value(app)
    assert test_field is not None, "No field with values found in test app"
    obj.get_data(filters={test_field: test_value})

    df_after = obj.get_data()
    assert len(df_before) == len(df_after)


def test_object_get_data_with_invalid_filter_value_raises_error(app_factory):
    """validate_filters=True (default) rejects values that don't exist in the field."""
    app = app_factory()
    sheet = app.sheets[VISUALS_SHEET_NAME]
    sheet.load()

    obj = sheet.objects[EXPORT_OBJECT_ID]
    test_field = list(app.fields.children.keys())[0]

    with pytest.raises(ValueError, match="values not found"):
        obj.get_data(filters={test_field: 204654321})


def test_object_get_data_unknown_field_raises_value_error(app_factory):
    """validate_filters=True (default) catches non-existent field names."""
    app = app_factory()
    sheet = app.sheets[VISUALS_SHEET_NAME]
    sheet.load()

    obj = sheet.objects[EXPORT_OBJECT_ID]
    with pytest.raises(ValueError, match="not found in the data model"):
        obj.get_data(filters={"NonExistentField_XYZ_12345": 1})


def test_object_get_data_validation_skipped_when_off(app_factory):
    """validate_filters=False skips field name check."""
    import pandas as pd
    app = app_factory()
    sheet = app.sheets[VISUALS_SHEET_NAME]
    sheet.load()

    obj = sheet.objects[EXPORT_OBJECT_ID]
    df = obj.get_data(filters={"NonExistentField_XYZ_12345": 1},
                      validate_filters=False)
    assert df is None or isinstance(df, pd.DataFrame)


def test_get_layout_works_for_master_items_sheet_object_and_bookmark(app_factory, name_factory, cleanup_registry):
    measure_name = name_factory("NewMs123")
    dimension_name = name_factory("NewDim123")
    variable_name = name_factory("NewVar123")
    app = app_factory()

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "measures", measure_name)
    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "dimensions", dimension_name)
    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "variables", variable_name)

    # #region agent log
    import json as _json, time as _time
    _logpath = "debug-f19121.log"
    def _dlog(loc, msg, data):
        with open(_logpath, "a", encoding="utf-8") as _f:
            _f.write(_json.dumps({"sessionId":"f19121","location":loc,"message":msg,"data":data,"timestamp":int(_time.time()*1000),"runId":"post-fix","hypothesisId":"A"}) + "\n")
    # #endregion

    # #region agent log
    _ms_result = app.measures.add(measure_name, "SomeDef")
    _dlog("test:160", "measures.add result", {"value": str(_ms_result), "type": str(type(_ms_result))})
    assert _ms_result is not None
    # #endregion

    # #region agent log
    _dim_result = app.dimensions.add(dimension_name, "SomeDef")
    _dlog("test:161", "dimensions.add result", {"value": str(_dim_result), "type": str(type(_dim_result))})
    assert len(_dim_result) > 0
    # #endregion

    # #region agent log
    _var_result = app.variables.add(variable_name, "SomeVar")
    _dlog("test:162", "variables.add result", {"value": str(_var_result), "type": str(type(_var_result))})
    assert _var_result is not None
    # #endregion

    measure_layout = app.measures[measure_name].get_layout()
    dimension_layout = app.dimensions[dimension_name].get_layout()
    variable_layout = app.variables[variable_name].get_layout()
    sheet_layout = app.sheets[VISUALS_SHEET_NAME].get_layout()

    sheet = app.sheets[VISUALS_SHEET_NAME]
    sheet.load()
    object_layout = sheet.objects[EXPORT_OBJECT_ID].get_layout()
    bookmark_layout = app.bookmarks[BOOKMARK_NAME].get_layout()

    # #region agent log
    _dlog("test:174-179", "layout assertions", {
        "measure_title": measure_layout.get("result",{}).get("qLayout",{}).get("qMeta",{}).get("title"),
        "dimension_title": dimension_layout.get("result",{}).get("qLayout",{}).get("qMeta",{}).get("title"),
        "variable_text": variable_layout.get("result",{}).get("qLayout",{}).get("qText"),
        "sheet_title": sheet_layout.get("result",{}).get("qLayout",{}).get("qMeta",{}).get("title"),
        "object_id": object_layout.get("result",{}).get("qLayout",{}).get("qInfo",{}).get("qId"),
        "bookmark_id": bookmark_layout.get("result",{}).get("qLayout",{}).get("qInfo",{}).get("qId"),
    })
    # #endregion

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
