from __future__ import annotations

import pytest

from ._integration_helpers import MAIN_APP_NAME, TARGET_APP_NAME, get_item_or_false, register_child_cleanup


pytestmark = [pytest.mark.integration]


def test_measure_create_with_full_metadata_persists(app_factory, name_factory, cleanup_registry):
    measure_name = name_factory("NewMs")
    app = app_factory()

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "measures", measure_name)

    result = app.measures.add(
        measure_name,
        definition="NewMsDef",
        description="desc",
        label="lbl",
        label_expression="lblEx",
        base_color="#f13f97",
    )
    assert result is not None
    assert app.measures[measure_name].definition == "NewMsDef"
    assert app.measures[measure_name].description == "desc"
    assert app.measures[measure_name].label == "lbl"
    assert app.measures[measure_name].label_expression == "lblEx"
    assert app.measures[measure_name].base_color == "#f13f97"

    app.save()
    app = app_factory()

    assert app.measures[measure_name].definition == "NewMsDef"
    assert app.measures[measure_name].description == "desc"
    assert app.measures[measure_name].label == "lbl"
    assert app.measures[measure_name].label_expression == "lblEx"
    assert app.measures[measure_name].base_color == "#f13f97"


def test_measure_delete_removes_from_app_and_engine(app_factory, name_factory, cleanup_registry):
    measure_name = name_factory("NewDelMs")
    app = app_factory()

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "measures", measure_name)

    assert app.measures.add(measure_name, definition="NewVarDef1") is not None
    app.save()
    app = app_factory()

    assert len(app.measures.df[app.measures.df["qMeta.title"] == measure_name]) >= 1
    assert app.measures[measure_name].delete() is True
    assert len(app.measures.df[app.measures.df["qMeta.title"] == measure_name]) == 0
    assert get_item_or_false(app.measures, measure_name) is False

    app.save()
    app = app_factory()

    assert len(app.measures.df[app.measures.df["qMeta.title"] == measure_name]) == 0
    assert get_item_or_false(app.measures, measure_name) is False


def test_measure_delete_missing_returns_false(app_factory, name_factory):
    missing_name = name_factory("NonExistentDelMs")
    app = app_factory()

    try:
        result = app.measures[missing_name].delete()
    except Exception:
        result = False

    assert result is False


def test_measure_update_full_metadata_and_format_persists(app_factory, name_factory, cleanup_registry):
    measure_name = name_factory("NewMsUpd")
    app = app_factory()

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "measures", measure_name)

    assert app.measures.add(
        measure_name,
        definition="NewMsDef",
        description="desc",
        label="lbl",
        label_expression="lblEx",
    ) is not None

    result = app.measures[measure_name].update(
        definition="UpdatedDef",
        label="UpdatedLabel",
        label_expression="UpdatedLblEx",
        description="desc",
        format_type="F",
        format_ndec=2,
        format_use_thou=0,
        format_dec=".",
        format_thou=",",
        base_color="#931f79",
    )
    assert result is True
    assert app.measures[measure_name].definition == "UpdatedDef"
    assert app.measures[measure_name].label == "UpdatedLabel"
    assert app.measures[measure_name].label_expression == "UpdatedLblEx"
    assert app.measures[measure_name].description == "desc"
    assert app.measures[measure_name].format_type == "F"
    assert app.measures[measure_name].format_ndec == 2
    assert app.measures[measure_name].format_use_thou == 0
    assert app.measures[measure_name].format_dec == "."
    assert app.measures[measure_name].format_thou == ","
    assert app.measures[measure_name].base_color == "#931f79"

    app.save()
    app = app_factory()

    assert app.measures[measure_name].definition == "UpdatedDef"
    assert app.measures[measure_name].label == "UpdatedLabel"
    assert app.measures[measure_name].label_expression == "UpdatedLblEx"
    assert app.measures[measure_name].description == "desc"
    assert app.measures[measure_name].format_type == "F"
    assert app.measures[measure_name].format_ndec == 2
    assert app.measures[measure_name].format_use_thou == 0
    assert app.measures[measure_name].format_dec == "."
    assert app.measures[measure_name].format_thou == ","
    assert app.measures[measure_name].base_color == "#931f79"


def test_measure_rename_persists(app_factory, name_factory, cleanup_registry):
    old_name = name_factory("NewMsRename")
    new_name = name_factory("NewMsRenamed")
    app = app_factory()

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "measures", old_name)
    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "measures", new_name)

    assert app.measures.add(
        old_name,
        definition="NewMsDef",
        description="desc",
        label="lbl",
        label_expression="lblEx",
    ) is not None

    assert app.measures[old_name].rename(new_name) is True
    assert app.measures[new_name].name == new_name
    assert app.measures.df[app.measures.df["qMeta.title"] == new_name]["qMeta.title"].values[0] == new_name

    app.save()
    app = app_factory()

    assert app.measures[new_name].name == new_name
    assert app.measures.df[app.measures.df["qMeta.title"] == new_name]["qMeta.title"].values[0] == new_name


def test_measure_add_from_source_copies_to_target_app(app_factory, name_factory, cleanup_registry):
    measure_name = name_factory("NewMs40")
    source_app = app_factory()
    target_app = app_factory(app_name=TARGET_APP_NAME)

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "measures", measure_name)
    register_child_cleanup(cleanup_registry, app_factory, TARGET_APP_NAME, "measures", measure_name)

    assert source_app.measures.add(
        measure_name,
        definition="NewMsDef",
        description="desc",
        label="lbl",
        label_expression="lblEx",
        base_color="#f13f97",
    ) is not None
    assert target_app.measures.add(source=source_app.measures[measure_name]) is not None

    target_app.save()
    target_app = app_factory(app_name=TARGET_APP_NAME)

    assert target_app.measures[measure_name].definition == "NewMsDef"
    assert target_app.measures[measure_name].description == "desc"
    assert target_app.measures[measure_name].label == "lbl"
    assert target_app.measures[measure_name].label_expression == "lblEx"
    assert target_app.measures[measure_name].base_color == "#f13f97"


def test_measure_copy_shortcut_copies_to_target_app(app_factory, name_factory, cleanup_registry):
    measure_name = name_factory("NewMs402")
    source_app = app_factory()
    target_app = app_factory(app_name=TARGET_APP_NAME)

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "measures", measure_name)
    register_child_cleanup(cleanup_registry, app_factory, TARGET_APP_NAME, "measures", measure_name)

    assert source_app.measures.add(
        measure_name,
        definition="NewMsDef",
        description="desc",
        label="lbl",
        label_expression="lblEx",
        base_color="#f13f97",
    ) is not None

    result = source_app.measures[measure_name].copy(target_app=target_app)
    assert len(result) > 0

    target_app.save()
    target_app = app_factory(app_name=TARGET_APP_NAME)

    assert target_app.measures[measure_name].definition == "NewMsDef"
