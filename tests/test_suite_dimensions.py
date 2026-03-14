from __future__ import annotations

import pytest

from ._integration_helpers import MAIN_APP_NAME, TARGET_APP_NAME, get_item_or_false, register_child_cleanup


pytestmark = [pytest.mark.integration]


def test_existing_complex_dimension_loads_lists(app_factory):
    app = app_factory()
    dimension = app.dimensions["Сложное измерение"]

    assert dimension.definition == ["Год", "Месяц", "Дата"]
    assert dimension.label == []
    assert dimension.base_color == "#4477aa"


def test_dimension_create_persists(app_factory, name_factory, cleanup_registry):
    dimension_name = name_factory("NewDim")
    app = app_factory()

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "dimensions", dimension_name)

    result = app.dimensions.add(dimension_name, definition="NewDimDef", label="lbl", base_color="#931f79")
    assert len(result) > 0
    assert app.dimensions[dimension_name].name == dimension_name
    assert app.dimensions[dimension_name].definition == ["NewDimDef"]
    assert app.dimensions[dimension_name].label == ["lbl"]
    assert app.dimensions[dimension_name].base_color == "#931f79"

    app.save()
    app = app_factory()

    assert app.dimensions[dimension_name].definition == ["NewDimDef"]
    assert app.dimensions[dimension_name].label == ["lbl"]
    assert app.dimensions[dimension_name].base_color == "#931f79"


def test_dimension_delete_removes_from_app_and_engine(app_factory, name_factory, cleanup_registry):
    dimension_name = name_factory("NewDimDel")
    app = app_factory()

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "dimensions", dimension_name)

    assert len(app.dimensions.add(dimension_name, definition="NewDimDefDel", label="lblDel")) > 0
    assert app.dimensions[dimension_name].delete() is True
    assert app.dimensions.df[app.dimensions.df["qMeta.title"] == dimension_name].empty is True
    assert get_item_or_false(app.dimensions, dimension_name) is False

    app.save()
    app = app_factory()

    assert app.dimensions.df[app.dimensions.df["qMeta.title"] == dimension_name].empty is True
    assert get_item_or_false(app.dimensions, dimension_name) is False


def test_dimension_delete_missing_returns_false(app_factory, name_factory):
    missing_name = name_factory("NonExistentDelDim")
    app = app_factory()

    try:
        result = app.dimensions[missing_name].delete()
    except Exception:
        result = False

    assert result is False


def test_dimension_update_persists(app_factory, name_factory, cleanup_registry):
    dimension_name = name_factory("NewDimUpd")
    app = app_factory()

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "dimensions", dimension_name)

    assert len(app.dimensions.add(dimension_name, definition="NewDimDefUpd", label="lblUpd")) > 0
    assert app.dimensions[dimension_name].update(
        definition="NewDimDefUpd2",
        label="lblUpd2",
        base_color="#931f79",
    ) is True
    assert app.dimensions[dimension_name].definition == ["NewDimDefUpd2"]
    assert app.dimensions[dimension_name].label == ["lblUpd2"]
    assert app.dimensions[dimension_name].base_color == "#931f79"

    app.save()
    app = app_factory()

    assert app.dimensions[dimension_name].definition == ["NewDimDefUpd2"]
    assert app.dimensions[dimension_name].label == ["lblUpd2"]
    assert app.dimensions[dimension_name].base_color == "#931f79"


def test_dimension_update_persists_multiple_field_defs(app_factory, name_factory, cleanup_registry):
    dimension_name = name_factory("NewDimMulti")
    app = app_factory()

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "dimensions", dimension_name)

    assert app.dimensions.add(
        dimension_name,
        definition=["Год", "Месяц"],
        label=["Год", "Месяц"],
        base_color="#4477aa",
    )
    assert app.dimensions[dimension_name].definition == ["Год", "Месяц"]
    assert app.dimensions[dimension_name].label == ["Год", "Месяц"]

    assert app.dimensions[dimension_name].update(
        definition=["Год", "Месяц", "Дата"],
        label=["Год", "Месяц", "Дата"],
        base_color="#931f79",
    ) is True
    assert app.dimensions[dimension_name].definition == ["Год", "Месяц", "Дата"]
    assert app.dimensions[dimension_name].label == ["Год", "Месяц", "Дата"]
    assert app.dimensions[dimension_name].base_color == "#931f79"

    app.save()
    app = app_factory()

    assert app.dimensions[dimension_name].definition == ["Год", "Месяц", "Дата"]
    assert app.dimensions[dimension_name].label == ["Год", "Месяц", "Дата"]
    assert app.dimensions[dimension_name].base_color == "#931f79"


def test_dimension_rename_persists(app_factory, name_factory, cleanup_registry):
    old_name = name_factory("NewDimRename")
    new_name = name_factory("NewDimRenamed")
    app = app_factory()

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "dimensions", old_name)
    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "dimensions", new_name)

    assert len(app.dimensions.add(old_name, definition="NewDimDefRename", label="lblRename")) > 0
    assert app.dimensions[old_name].rename(new_name) is True
    assert app.dimensions[new_name].name == new_name
    assert app.dimensions.df[app.dimensions.df["qMeta.title"] == new_name]["qMeta.title"].values[0] == new_name

    app.save()
    app = app_factory()

    assert app.dimensions[new_name].name == new_name
    assert app.dimensions.df[app.dimensions.df["qMeta.title"] == new_name]["qMeta.title"].values[0] == new_name


def test_dimension_add_from_source_copies_to_target_app(app_factory, name_factory, cleanup_registry):
    dimension_name = name_factory("NewDim50")
    source_app = app_factory()
    target_app = app_factory(app_name=TARGET_APP_NAME)

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "dimensions", dimension_name)
    register_child_cleanup(cleanup_registry, app_factory, TARGET_APP_NAME, "dimensions", dimension_name)

    assert len(source_app.dimensions.add(
        dimension_name,
        definition="NewDimDef",
        label="lbl",
        base_color="#931f79",
    )) > 0
    assert len(target_app.dimensions.add(source=source_app.dimensions[dimension_name])) > 0

    target_app.save()
    target_app = app_factory(app_name=TARGET_APP_NAME)

    assert target_app.dimensions[dimension_name].definition == ["NewDimDef"]
    assert target_app.dimensions[dimension_name].label == ["lbl"]
    assert target_app.dimensions[dimension_name].base_color == "#931f79"


def test_dimension_copy_shortcut_copies_to_target_app(app_factory, name_factory, cleanup_registry):
    dimension_name = name_factory("NewDim501")
    source_app = app_factory()
    target_app = app_factory(app_name=TARGET_APP_NAME)

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "dimensions", dimension_name)
    register_child_cleanup(cleanup_registry, app_factory, TARGET_APP_NAME, "dimensions", dimension_name)

    assert len(source_app.dimensions.add(
        dimension_name,
        definition="NewDimDef",
        label="lbl",
        base_color="#931f79",
    )) > 0

    result = source_app.dimensions[dimension_name].copy(target_app=target_app)
    assert len(result) > 0

    target_app.save()
    target_app = app_factory(app_name=TARGET_APP_NAME)

    assert target_app.dimensions[dimension_name].definition == ["NewDimDef"]
