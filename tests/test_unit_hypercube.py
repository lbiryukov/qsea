"""Unit tests for _get_hypercube_data() with mocked query/layout.

These tests do NOT require a live Qlik Sense connection.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, call

import pandas as pd
import pytest

import qsea


def _make_layout(dim_info, ms_info, total_rows, total_cols):
    """Build a GetLayout-style response dict."""
    return {
        "result": {
            "qLayout": {
                "qHyperCube": {
                    "qSize": {"qcx": total_cols, "qcy": total_rows},
                    "qDimensionInfo": dim_info,
                    "qMeasureInfo": ms_info,
                    "qDataPages": [],
                }
            }
        }
    }


def _make_page_result(matrix):
    """Build a GetHyperCubeData-style response dict."""
    return {
        "result": {
            "qDataPages": [{"qMatrix": matrix}]
        }
    }


def _cell(text, num=None, is_numeric=False):
    cell = {"qText": text}
    if num is not None:
        cell["qNum"] = num
    if is_numeric:
        cell["qIsNumeric"] = True
    return cell


class TestEmptyDataset:
    @patch("qsea._loaders._get_layout")
    def test_returns_empty_dataframe_with_correct_columns(self, mock_layout):
        mock_layout.return_value = _make_layout(
            dim_info=[{"qFallbackTitle": "City"}],
            ms_info=[{"qFallbackTitle": "Sales"}],
            total_rows=0,
            total_cols=2,
        )

        df = qsea._get_hypercube_data(MagicMock(), handle=1)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert list(df.columns) == ["City", "Sales"]


class TestSinglePage:
    @patch("qsea._loaders.query")
    @patch("qsea._loaders._get_layout")
    def test_returns_all_rows_in_single_page(self, mock_layout, mock_query):
        mock_layout.return_value = _make_layout(
            dim_info=[{"qFallbackTitle": "City"}],
            ms_info=[{"qFallbackTitle": "Revenue"}],
            total_rows=3,
            total_cols=2,
        )

        mock_query.return_value = _make_page_result([
            [_cell("Moscow"), _cell("100", num=100.0)],
            [_cell("London"), _cell("200", num=200.0)],
            [_cell("Berlin"), _cell("300", num=300.0)],
        ])

        df = qsea._get_hypercube_data(MagicMock(), handle=1)
        assert len(df) == 3
        assert list(df.columns) == ["City", "Revenue"]
        assert list(df["City"]) == ["Moscow", "London", "Berlin"]
        assert list(df["Revenue"]) == [100.0, 200.0, 300.0]


class TestPagination:
    @patch("qsea._loaders.query")
    @patch("qsea._loaders._get_layout")
    def test_fetches_multiple_pages(self, mock_layout, mock_query):
        total_cols = 2
        page_height = 10000 // total_cols  # 5000

        mock_layout.return_value = _make_layout(
            dim_info=[{"qFallbackTitle": "ID"}],
            ms_info=[{"qFallbackTitle": "Val"}],
            total_rows=7500,
            total_cols=total_cols,
        )

        page1_rows = [[_cell(str(i)), _cell(str(i), num=float(i))] for i in range(5000)]
        page2_rows = [[_cell(str(i)), _cell(str(i), num=float(i))] for i in range(5000, 7500)]

        mock_query.side_effect = [
            _make_page_result(page1_rows),
            _make_page_result(page2_rows),
        ]

        df = qsea._get_hypercube_data(MagicMock(), handle=1)
        assert len(df) == 7500

        page_calls = mock_query.call_args_list
        assert len(page_calls) == 2
        params1 = page_calls[0][0][1]["params"][1][0]
        assert params1["qTop"] == 0
        assert params1["qHeight"] == 5000
        params2 = page_calls[1][0][1]["params"][1][0]
        assert params2["qTop"] == 5000
        assert params2["qHeight"] == 2500


class TestDimensionMeasureParsing:
    @patch("qsea._loaders.query")
    @patch("qsea._loaders._get_layout")
    def test_dimensions_use_qtext_measures_use_qnum(self, mock_layout, mock_query):
        mock_layout.return_value = _make_layout(
            dim_info=[{"qFallbackTitle": "Region"}, {"qFallbackTitle": "Year"}],
            ms_info=[{"qFallbackTitle": "Amount"}],
            total_rows=1,
            total_cols=3,
        )

        mock_query.return_value = _make_page_result([
            [_cell("North"), _cell("2025"), _cell("999", num=999.0)],
        ])

        df = qsea._get_hypercube_data(MagicMock(), handle=1)
        assert df.iloc[0]["Region"] == "North"
        assert df.iloc[0]["Year"] == "2025"
        assert df.iloc[0]["Amount"] == 999.0

    @patch("qsea._loaders.query")
    @patch("qsea._loaders._get_layout")
    def test_nan_measure_falls_back_to_qtext(self, mock_layout, mock_query):
        mock_layout.return_value = _make_layout(
            dim_info=[{"qFallbackTitle": "D"}],
            ms_info=[{"qFallbackTitle": "M"}],
            total_rows=1,
            total_cols=2,
        )

        mock_query.return_value = _make_page_result([
            [_cell("X"), _cell("-", num=float("nan"))],
        ])

        df = qsea._get_hypercube_data(MagicMock(), handle=1)
        assert df.iloc[0]["M"] == "-"


class TestFallbackColumnNames:
    @patch("qsea._loaders._get_layout")
    def test_uses_fallback_names_when_titles_missing(self, mock_layout):
        mock_layout.return_value = _make_layout(
            dim_info=[{}],
            ms_info=[{}],
            total_rows=0,
            total_cols=2,
        )

        df = qsea._get_hypercube_data(MagicMock(), handle=1)
        assert list(df.columns) == ["dim_0", "ms_0"]


class TestLayoutErrors:
    @patch("qsea._loaders._get_layout")
    def test_raises_on_missing_layout(self, mock_layout):
        mock_layout.return_value = None
        with pytest.raises(ValueError, match="unexpected structure"):
            qsea._get_hypercube_data(MagicMock(), handle=1)

    @patch("qsea._loaders._get_layout")
    def test_raises_on_missing_hypercube(self, mock_layout):
        mock_layout.return_value = {"result": {"qLayout": {}}}
        with pytest.raises(ValueError, match="does not contain a hypercube"):
            qsea._get_hypercube_data(MagicMock(), handle=1)

    @patch("qsea._loaders.query")
    @patch("qsea._loaders._get_layout")
    def test_raises_on_failed_page_fetch(self, mock_layout, mock_query):
        mock_layout.return_value = _make_layout(
            dim_info=[{"qFallbackTitle": "D"}],
            ms_info=[{"qFallbackTitle": "M"}],
            total_rows=10,
            total_cols=2,
        )
        mock_query.return_value = None

        with pytest.raises(ValueError, match="GetHyperCubeData failed"):
            qsea._get_hypercube_data(MagicMock(), handle=1)
