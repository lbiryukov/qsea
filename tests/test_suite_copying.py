from __future__ import annotations

import pytest

from ._integration_helpers import (
    COPY_OBJECT_SOURCE_ID,
    COPY_OBJECT_SOURCE_SHEET,
    COPY_OBJECT_TARGET_SHEET,
    COPY_SHEET_MEASURE_NAME,
    COPY_SHEET_OBJECT_ID,
    COPY_SHEET_SOURCE_NAME,
    MAIN_APP_NAME,
    TARGET_APP_NAME,
    register_sheet_cleanup,
    register_sheet_clear_cleanup,
)


pytestmark = [pytest.mark.integration]


def test_sheet_create_persists(app_factory, name_factory, cleanup_registry):
    sheet_name = name_factory("NewSheet")
    app = app_factory()

    register_sheet_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, sheet_name)

    assert app.sheets.add(name=sheet_name, description="SomeDescription") is not None
    assert len(app.sheets.df[app.sheets.df["qMeta.title"] == sheet_name]) == 1
    assert app.sheets.df[app.sheets.df["qMeta.title"] == sheet_name]["qMeta.description"].values[0] == "SomeDescription"

    app.save()
    app = app_factory()

    assert len(app.sheets.df[app.sheets.df["qMeta.title"] == sheet_name]) == 1
    assert app.sheets.df[app.sheets.df["qMeta.title"] == sheet_name]["qMeta.description"].values[0] == "SomeDescription"


def test_object_copy_to_target_sheet_preserves_measure_and_dimension_counts(app_factory, cleanup_registry):
    source_app = app_factory()
    target_app = app_factory(app_name=TARGET_APP_NAME)

    register_sheet_clear_cleanup(cleanup_registry, app_factory, TARGET_APP_NAME, COPY_OBJECT_TARGET_SHEET)

    source_app.sheets.load()
    source_sheet = source_app.sheets[COPY_OBJECT_SOURCE_SHEET]
    source_sheet.load()
    source_object = source_sheet.objects[COPY_OBJECT_SOURCE_ID]
    source_object.load()

    target_app.sheets.load()
    target_sheet = target_app.sheets[COPY_OBJECT_TARGET_SHEET]
    assert target_sheet.clear() is True
    assert source_object.copy(target_app, target_sheet) is not None

    target_app.save()
    target_app = app_factory(app_name=TARGET_APP_NAME)
    target_app.sheets.load()
    target_sheet = target_app.sheets[COPY_OBJECT_TARGET_SHEET]
    target_sheet.load()

    target_object_id = target_sheet.objects.df.iloc[0]["name"]
    target_object = target_sheet.objects[target_object_id]
    target_object.load()

    assert len(target_object.measures.df) == len(source_object.measures.df)
    assert len(target_object.dimensions.df) == len(source_object.dimensions.df)


def test_target_sheet_clear_removes_all_objects(app_factory, cleanup_registry):
    source_app = app_factory()
    target_app = app_factory(app_name=TARGET_APP_NAME)

    register_sheet_clear_cleanup(cleanup_registry, app_factory, TARGET_APP_NAME, COPY_OBJECT_TARGET_SHEET)

    source_app.sheets.load()
    source_sheet = source_app.sheets[COPY_OBJECT_SOURCE_SHEET]
    source_sheet.load()
    source_object = source_sheet.objects[COPY_OBJECT_SOURCE_ID]
    source_object.load()

    target_app.sheets.load()
    target_sheet = target_app.sheets[COPY_OBJECT_TARGET_SHEET]
    assert target_sheet.clear() is True
    assert source_object.copy(target_app, target_sheet) is not None
    target_app.save()

    target_app = app_factory(app_name=TARGET_APP_NAME)
    target_app.sheets.load()
    target_sheet = target_app.sheets[COPY_OBJECT_TARGET_SHEET]
    assert target_sheet.clear() is True
    assert len(target_sheet.objects.df) == 0

    target_app = app_factory(app_name=TARGET_APP_NAME)
    target_app.sheets.load()
    target_sheet = target_app.sheets[COPY_OBJECT_TARGET_SHEET]
    target_sheet.load()
    assert len(target_sheet.objects.df) == 0


@pytest.mark.slow
def test_sheet_copy_to_target_app_preserves_object_count_and_remaps_library_ids(app_factory, cleanup_registry):
    source_app = app_factory()
    target_app = app_factory(app_name=TARGET_APP_NAME)

    register_sheet_cleanup(cleanup_registry, app_factory, TARGET_APP_NAME, COPY_SHEET_SOURCE_NAME)

    target_app.sheets.load()
    try:
        existing_sheet = target_app.sheets[COPY_SHEET_SOURCE_NAME]
        existing_sheet.delete()
        target_app.save()
    except Exception:
        pass

    source_app.sheets.load()
    source_sheet = source_app.sheets[COPY_SHEET_SOURCE_NAME]
    assert source_sheet.copy(target_app) is True

    assert COPY_SHEET_SOURCE_NAME in target_app.sheets.df["qMeta.title"].values
    target_sheet = target_app.sheets[COPY_SHEET_SOURCE_NAME]
    target_sheet.load()
    source_sheet.load()
    assert len(target_sheet.objects.df) == len(source_sheet.objects.df)

    target_app.save()
    target_app = app_factory(app_name=TARGET_APP_NAME)
    target_app.sheets.load()
    target_sheet = target_app.sheets[COPY_SHEET_SOURCE_NAME]
    target_sheet.load()

    assert len(target_sheet.objects.df) == len(source_sheet.objects.df)

    source_sheet.objects[COPY_SHEET_OBJECT_ID].load()
    target_sheet.objects[COPY_SHEET_OBJECT_ID].load()
    source_df = source_sheet.objects[COPY_SHEET_OBJECT_ID].measures.df
    target_df = target_sheet.objects[COPY_SHEET_OBJECT_ID].measures.df
    source_app.measures.load()
    target_app.measures.load()
    source_measure_id = source_app.measures[COPY_SHEET_MEASURE_NAME].id
    target_measure_id = target_app.measures[COPY_SHEET_MEASURE_NAME].id

    assert source_measure_id in source_df["qLibraryId"].values
    assert target_measure_id in target_df["qLibraryId"].values
