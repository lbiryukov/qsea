from __future__ import annotations

import pytest

import qsea

from ._integration_helpers import (
    MAIN_APP_NAME,
    RATING_SHEET_NAME,
    VISUALS_SHEET_NAME,
    BOOKMARK_NAME,
    register_child_cleanup,
)


pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Lazy-loading: collections load automatically on first access
# ---------------------------------------------------------------------------

class TestLazyLoading:
    def test_collection_not_loaded_initially(self, connection):
        app = qsea.App(connection, MAIN_APP_NAME)
        assert app.variables._loaded is False
        assert app.measures._loaded is False
        assert app.dimensions._loaded is False
        assert app.sheets._loaded is False
        assert app.fields._loaded is False
        assert app.bookmarks._loaded is False

    def test_getitem_triggers_lazy_load(self, connection):
        app = qsea.App(connection, MAIN_APP_NAME)
        assert app.variables._loaded is False
        first_var = next(iter(app.variables.children.values())) if app.variables._loaded else None
        if first_var is None:
            app.variables.load()
            first_var = next(iter(app.variables.children.values()))
            app2 = qsea.App(connection, MAIN_APP_NAME)
            fetched = app2.variables[first_var.name]
            assert app2.variables._loaded is True
            assert fetched.name == first_var.name

    def test_iter_triggers_lazy_load(self, connection):
        app = qsea.App(connection, MAIN_APP_NAME)
        assert app.measures._loaded is False
        names = [ms.name for ms in app.measures]
        assert app.measures._loaded is True
        assert len(names) > 0

    def test_len_triggers_lazy_load(self, connection):
        app = qsea.App(connection, MAIN_APP_NAME)
        assert app.sheets._loaded is False
        count = len(app.sheets)
        assert app.sheets._loaded is True
        assert count > 0

    def test_contains_triggers_lazy_load(self, connection):
        app = qsea.App(connection, MAIN_APP_NAME)
        assert app.dimensions._loaded is False
        app2 = qsea.App(connection, MAIN_APP_NAME)
        app2.dimensions.load()
        first_dim_name = next(iter(app2.dimensions.children.keys()))
        result = first_dim_name in app.dimensions
        assert app.dimensions._loaded is True
        assert result is True

    def test_df_property_triggers_lazy_load(self, connection):
        app = qsea.App(connection, MAIN_APP_NAME)
        assert app.measures._loaded is False
        df = app.measures.df
        assert app.measures._loaded is True
        assert df is not None
        assert len(df) > 0

    def test_explicit_load_sets_loaded_flag(self, connection):
        app = qsea.App(connection, MAIN_APP_NAME)
        assert app.variables._loaded is False
        app.variables.load()
        assert app.variables._loaded is True

    def test_double_load_still_works(self, connection):
        app = qsea.App(connection, MAIN_APP_NAME)
        app.variables.load()
        count1 = app.variables.count
        app.variables.load()
        count2 = app.variables.count
        assert count1 == count2

    def test_app_load_sets_all_loaded_flags(self, connection):
        app = qsea.App(connection, MAIN_APP_NAME)
        app.load()
        assert app.variables._loaded is True
        assert app.measures._loaded is True
        assert app.dimensions._loaded is True
        assert app.sheets._loaded is True
        assert app.fields._loaded is True
        assert app.bookmarks._loaded is True

    def test_lazy_load_results_match_explicit_load(self, connection):
        app_explicit = qsea.App(connection, MAIN_APP_NAME)
        app_explicit.load()
        explicit_var_names = set(app_explicit.variables.children.keys())
        explicit_ms_names = set(app_explicit.measures.children.keys())

        app_lazy = qsea.App(connection, MAIN_APP_NAME)
        lazy_var_names = set(v.name for v in app_lazy.variables)
        lazy_ms_names = set(m.name for m in app_lazy.measures)

        assert explicit_var_names == lazy_var_names
        assert explicit_ms_names == lazy_ms_names


# ---------------------------------------------------------------------------
# Fast single-object loading via get()
# ---------------------------------------------------------------------------

class TestGetSingleObject:
    def test_get_variable_by_name_without_full_load(self, connection):
        app_ref = qsea.App(connection, MAIN_APP_NAME)
        app_ref.variables.load()
        first_var = next(iter(app_ref.variables.children.values()))

        app = qsea.App(connection, MAIN_APP_NAME)
        var = app.variables.get(name=first_var.name)
        assert var is not None
        assert var.name == first_var.name
        assert var.id == first_var.id
        assert app.variables._loaded is False

    def test_get_variable_by_id_without_full_load(self, connection):
        app_ref = qsea.App(connection, MAIN_APP_NAME)
        app_ref.variables.load()
        first_var = next(iter(app_ref.variables.children.values()))

        app = qsea.App(connection, MAIN_APP_NAME)
        var = app.variables.get(id=first_var.id)
        assert var is not None
        assert var.name == first_var.name
        assert app.variables._loaded is False

    def test_get_measure_by_name_without_full_load(self, connection):
        app_ref = qsea.App(connection, MAIN_APP_NAME)
        app_ref.measures.load()
        first_ms = next(iter(app_ref.measures.children.values()))

        app = qsea.App(connection, MAIN_APP_NAME)
        ms = app.measures.get(name=first_ms.name)
        assert ms is not None
        assert ms.name == first_ms.name
        assert ms.id == first_ms.id
        assert ms.definition == first_ms.definition
        assert app.measures._loaded is False

    def test_get_measure_by_id_without_full_load(self, connection):
        app_ref = qsea.App(connection, MAIN_APP_NAME)
        app_ref.measures.load()
        first_ms = next(iter(app_ref.measures.children.values()))

        app = qsea.App(connection, MAIN_APP_NAME)
        ms = app.measures.get(id=first_ms.id)
        assert ms is not None
        assert ms.name == first_ms.name
        assert app.measures._loaded is False

    def test_get_dimension_by_name_without_full_load(self, connection):
        app_ref = qsea.App(connection, MAIN_APP_NAME)
        app_ref.dimensions.load()
        first_dim = next(iter(app_ref.dimensions.children.values()))

        app = qsea.App(connection, MAIN_APP_NAME)
        dim = app.dimensions.get(name=first_dim.name)
        assert dim is not None
        assert dim.name == first_dim.name
        assert dim.id == first_dim.id
        assert app.dimensions._loaded is False

    def test_get_dimension_by_id_without_full_load(self, connection):
        app_ref = qsea.App(connection, MAIN_APP_NAME)
        app_ref.dimensions.load()
        first_dim = next(iter(app_ref.dimensions.children.values()))

        app = qsea.App(connection, MAIN_APP_NAME)
        dim = app.dimensions.get(id=first_dim.id)
        assert dim is not None
        assert dim.name == first_dim.name
        assert dim.definition == first_dim.definition
        assert app.dimensions._loaded is False

    def test_get_sheet_by_name_without_full_load(self, connection):
        app = qsea.App(connection, MAIN_APP_NAME)
        sh = app.sheets.get(name=RATING_SHEET_NAME)
        assert sh is not None
        assert sh.name == RATING_SHEET_NAME
        assert sh.id != ''
        assert app.sheets._loaded is False

    def test_get_bookmark_by_name_without_full_load(self, connection):
        app = qsea.App(connection, MAIN_APP_NAME)
        bm = app.bookmarks.get(name=BOOKMARK_NAME)
        assert bm is not None
        assert bm.name == BOOKMARK_NAME
        assert bm.id != ''
        assert app.bookmarks._loaded is False

    def test_get_returns_none_for_missing_object(self, connection):
        app = qsea.App(connection, MAIN_APP_NAME)
        result = app.measures.get(name='NONEXISTENT_MEASURE_XYZ_12345')
        assert result is None

    def test_get_returns_none_for_missing_id(self, connection):
        app = qsea.App(connection, MAIN_APP_NAME)
        result = app.measures.get(id='00000000-0000-0000-0000-000000000000')
        assert result is None

    def test_get_raises_on_no_arguments(self, connection):
        app = qsea.App(connection, MAIN_APP_NAME)
        with pytest.raises(ValueError):
            app.measures.get()

    def test_get_caches_result_for_subsequent_access(self, connection):
        app = qsea.App(connection, MAIN_APP_NAME)
        ms1 = app.measures.get(name=next(iter(
            qsea.App(connection, MAIN_APP_NAME).measures.children.keys()
        )) if False else None)

        app_ref = qsea.App(connection, MAIN_APP_NAME)
        app_ref.measures.load()
        ref_name = next(iter(app_ref.measures.children.keys()))

        app2 = qsea.App(connection, MAIN_APP_NAME)
        ms1 = app2.measures.get(name=ref_name)
        assert ms1 is not None
        ms2 = app2.measures.get(name=ref_name)
        assert ms2 is ms1

    def test_get_then_full_load_still_works(self, connection):
        app_ref = qsea.App(connection, MAIN_APP_NAME)
        app_ref.measures.load()
        ref_name = next(iter(app_ref.measures.children.keys()))

        app = qsea.App(connection, MAIN_APP_NAME)
        ms_single = app.measures.get(name=ref_name)
        assert ms_single is not None

        app.measures.load()
        assert app.measures._loaded is True
        assert ref_name in app.measures.children
        assert app.measures.count > 1

    def test_get_from_already_loaded_collection(self, connection):
        app = qsea.App(connection, MAIN_APP_NAME)
        app.load()
        first_ms_name = next(iter(app.measures.children.keys()))
        ms = app.measures.get(name=first_ms_name)
        assert ms is not None
        assert ms.name == first_ms_name
