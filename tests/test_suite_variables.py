from __future__ import annotations

import pytest

from ._integration_helpers import MAIN_APP_NAME, get_item_or_false, register_child_cleanup


pytestmark = [pytest.mark.integration]


def test_variable_create_persists_in_memory_and_after_reload(app_factory, name_factory, cleanup_registry):
    variable_name = name_factory("NewVar")
    app = app_factory()

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "variables", variable_name)

    result = app.variables.add(variable_name, "NewVarDef1")
    assert result is not None
    assert len(app.variables.df[app.variables.df["qName"] == variable_name]) == 1
    assert app.variables.df[app.variables.df["qName"] == variable_name]["qDefinition"].values[0] == "NewVarDef1"

    app.save()
    app = app_factory()

    assert len(app.variables.df[app.variables.df["qName"] == variable_name]) == 1
    assert app.variables.df[app.variables.df["qName"] == variable_name]["qDefinition"].values[0] == "NewVarDef1"


def test_variable_update_definition_persists(app_factory, name_factory, cleanup_registry):
    variable_name = name_factory("NewVarUpd")
    app = app_factory()

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "variables", variable_name)

    assert app.variables.add(variable_name, "NewVarDef1") is not None
    variable = app.variables[variable_name]
    assert variable.update(definition="NewVarDef2") is True
    assert variable.definition == "NewVarDef2"
    assert app.variables.df[app.variables.df["qName"] == variable_name]["qDefinition"].values[0] == "NewVarDef2"

    app.save()
    app = app_factory()

    assert app.variables[variable_name].definition == "NewVarDef2"
    assert app.variables.df[app.variables.df["qName"] == variable_name]["qDefinition"].values[0] == "NewVarDef2"


def test_variable_delete_removes_from_app_and_engine(app_factory, name_factory, cleanup_registry):
    variable_name = name_factory("NewVarDel")
    app = app_factory()

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "variables", variable_name)

    assert app.variables.add(variable_name, "NewVarDef1") is not None
    app.save()
    app = app_factory()

    assert len(app.variables.df[app.variables.df["qName"] == variable_name]) == 1
    assert app.variables[variable_name].delete() is True
    assert len(app.variables.df[app.variables.df["qName"] == variable_name]) == 0
    assert get_item_or_false(app.variables, variable_name) is False

    app.save()
    app = app_factory()

    assert len(app.variables.df[app.variables.df["qName"] == variable_name]) == 0
    assert get_item_or_false(app.variables, variable_name) is False


def test_variable_delete_missing_returns_false(app_factory, name_factory):
    missing_name = name_factory("NonExistentVarDel")
    app = app_factory()

    try:
        result = app.variables[missing_name].delete()
    except Exception:
        result = False

    assert result is False


def test_variable_rename_persists(app_factory, name_factory, cleanup_registry):
    old_name = name_factory("NewVarRen")
    new_name = name_factory("NewVarRenamed")
    app = app_factory()

    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "variables", old_name)
    register_child_cleanup(cleanup_registry, app_factory, MAIN_APP_NAME, "variables", new_name)

    assert app.variables.add(old_name, "NewVarDef1") is not None
    assert app.variables[old_name].rename(new_name) is True
    assert app.variables[new_name].name == new_name
    assert app.variables.df[app.variables.df["qName"] == new_name]["qDefinition"].values[0] == "NewVarDef1"

    app.save()
    app = app_factory()

    assert app.variables[new_name].name == new_name
    assert app.variables.df[app.variables.df["qName"] == new_name]["qDefinition"].values[0] == "NewVarDef1"
