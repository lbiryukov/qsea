"""Unit tests for internal helper functions.

These tests do NOT require a live Qlik Sense connection.
"""
from __future__ import annotations

import logging

import qsea


class TestToQlik:
    def test_none_returns_empty_string(self):
        assert qsea._to_qlik(None) == ""

    def test_plain_string_is_quoted(self):
        assert qsea._to_qlik("hello") == '"hello"'

    def test_integer_is_quoted_as_string(self):
        assert qsea._to_qlik(42) == '"42"'

    def test_double_quotes_are_escaped(self):
        result = qsea._to_qlik('say "hi"')
        assert result == '"say \\"hi\\""'

    def test_backslash_is_escaped(self):
        result = qsea._to_qlik("back\\slash")
        assert result == '"back\\\\slash"'

    def test_empty_string_is_quoted(self):
        assert qsea._to_qlik("") == '""'


class TestFindKey:
    def test_top_level_key(self):
        assert qsea._find_key("a", {"a": 1, "b": 2}) is True

    def test_nested_key(self):
        assert qsea._find_key("c", {"a": {"b": {"c": 3}}}) is True

    def test_missing_key(self):
        assert qsea._find_key("z", {"a": 1}) is False

    def test_empty_dict(self):
        assert qsea._find_key("a", {}) is False

    def test_non_dict_values_are_skipped(self):
        assert qsea._find_key("b", {"a": [1, 2, 3]}) is False


class TestBuildSetModifier:
    def test_empty_dict_returns_empty_string(self):
        assert qsea._build_set_modifier({}) == ""

    def test_none_returns_empty_string(self):
        assert qsea._build_set_modifier(None) == ""

    def test_single_numeric_filter(self):
        assert qsea._build_set_modifier({"Year": 2025}) == "{<[Year]={2025}>}"

    def test_single_string_filter(self):
        assert qsea._build_set_modifier({"City": "Moscow"}) == "{<[City]={'Moscow'}>}"

    def test_list_of_values(self):
        result = qsea._build_set_modifier({"Year": [2024, 2025]})
        assert result == "{<[Year]={2024,2025}>}"

    def test_multiple_fields(self):
        result = qsea._build_set_modifier({"Year": 2025, "Month": 2})
        assert "[Year]={2025}" in result
        assert "[Month]={2}" in result
        assert result.startswith("{<")
        assert result.endswith(">}")

    def test_single_quote_in_value_is_escaped(self):
        result = qsea._build_set_modifier({"Name": "O'Brien"})
        assert "O''Brien" in result

    def test_float_value(self):
        result = qsea._build_set_modifier({"Price": 9.99})
        assert "9.99" in result

    def test_mixed_types_in_list(self):
        result = qsea._build_set_modifier({"Val": [1, "two", 3.0]})
        assert "1" in result
        assert "'two'" in result
        assert "3.0" in result


class TestConfig:
    def test_default_log_query_max_length(self):
        cfg = qsea.Config()
        assert cfg.logQueryMaxLength == 300

    def test_module_level_config_exists(self):
        assert hasattr(qsea, 'config')
        assert isinstance(qsea.config, qsea.Config)


class TestNullHandler:
    def test_library_logger_has_null_handler(self):
        lib_logger = logging.getLogger("qsea")
        handler_types = [type(h) for h in lib_logger.handlers]
        assert logging.NullHandler in handler_types


class TestSetupLogging:
    def test_default_log_level_is_info_constant(self):
        import inspect
        sig = inspect.signature(qsea.setup_logging)
        default = sig.parameters['log_level'].default
        assert default == logging.INFO
        assert isinstance(default, int)

    def test_log_file_path_is_optional(self):
        import inspect
        sig = inspect.signature(qsea.setup_logging)
        default = sig.parameters['log_file_path'].default
        assert default is None

    def test_stream_handler_when_no_path(self):
        lib_logger = logging.getLogger("qsea")
        before = len(lib_logger.handlers)
        qsea.setup_logging()
        try:
            new_handlers = lib_logger.handlers[before:]
            assert any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in new_handlers)
        finally:
            for h in new_handlers:
                lib_logger.removeHandler(h)

    def test_file_handler_creates_parent_dirs(self, tmp_path):
        log_path = tmp_path / "sub" / "dir" / "test.log"
        lib_logger = logging.getLogger("qsea")
        before = len(lib_logger.handlers)
        qsea.setup_logging(str(log_path))
        try:
            assert log_path.parent.exists()
            new_handlers = lib_logger.handlers[before:]
            assert any(isinstance(h, logging.FileHandler) for h in new_handlers)
        finally:
            for h in new_handlers:
                h.close()
                lib_logger.removeHandler(h)

    def test_does_not_affect_root_logger(self):
        root = logging.getLogger()
        root_handlers_before = list(root.handlers)
        lib_logger = logging.getLogger("qsea")
        before = len(lib_logger.handlers)
        qsea.setup_logging()
        try:
            assert root.handlers == root_handlers_before
        finally:
            for h in lib_logger.handlers[before:]:
                lib_logger.removeHandler(h)


class TestTestFunction:
    def test_returns_39(self):
        assert qsea._test() == 39
