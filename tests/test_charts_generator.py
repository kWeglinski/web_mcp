"""Unit tests for chart generation."""

from unittest.mock import MagicMock, patch

import pytest

from web_mcp.charts.generator import (
    CHART_BUILDERS,
    ChartConfig,
    ChartError,
    _build_figure,
    _create_area_chart,
    _create_bar_chart,
    _create_box_chart,
    _create_bubble_chart,
    _create_funnel_chart,
    _create_gauge_chart,
    _create_heatmap_chart,
    _create_histogram_chart,
    _create_indicator_chart,
    _create_line_chart,
    _create_pie_chart,
    _create_scatter_chart,
    _create_sunburst_chart,
    _create_treemap_chart,
    _extract_data_arrays,
    create_chart,
    create_chart_image,
    create_chart_image_bytes,
)


class TestChartConfig:
    def test_basic_config(self):
        config = ChartConfig(type="line", data={"x": [1, 2, 3], "y": [4, 5, 6]})
        assert config.type == "line"
        assert config.title == ""
        assert config.x_label == ""
        assert config.y_label == ""
        assert config.options == {}

    def test_config_with_all_fields(self):
        config = ChartConfig(
            type="bar",
            title="Test Chart",
            x_label="X Axis",
            y_label="Y Axis",
            data={"labels": ["A", "B"], "values": [10, 20]},
            options={"width": 800, "height": 600},
        )
        assert config.title == "Test Chart"
        assert config.x_label == "X Axis"
        assert config.y_label == "Y Axis"
        assert config.options["width"] == 800

    def test_config_default_options(self):
        config = ChartConfig(type="pie", data={"labels": ["A"], "values": [1]})
        assert config.options == {}


class TestExtractDataArrays:
    def test_simple_list_values(self):
        data = {"x": [1, 2, 3], "y": [4, 5, 6]}
        result = _extract_data_arrays(data)
        assert result == {"x": [1, 2, 3], "y": [4, 5, 6]}

    def test_nested_dict_values(self):
        data = {"data": {"x": [1, 2], "y": [3, 4]}}
        result = _extract_data_arrays(data)
        assert result == {"data_x": [1, 2], "data_y": [3, 4]}

    def test_scalar_values(self):
        data = {"value": 42}
        result = _extract_data_arrays(data)
        assert result == {"value": [42]}

    def test_mixed_values(self):
        data = {"x": [1, 2], "count": 5, "nested": {"a": [1, 2]}}
        result = _extract_data_arrays(data)
        assert result["x"] == [1, 2]
        assert result["count"] == [5]
        assert result["nested_a"] == [1, 2]

    def test_empty_dict(self):
        result = _extract_data_arrays({})
        assert result == {}


class TestChartBuilders:
    def test_all_chart_types_registered(self):
        expected = [
            "line",
            "bar",
            "scatter",
            "pie",
            "area",
            "histogram",
            "box",
            "heatmap",
            "treemap",
            "sunburst",
            "funnel",
            "gauge",
            "indicator",
            "bubble",
        ]
        for chart_type in expected:
            assert chart_type in CHART_BUILDERS

    def test_unknown_chart_type_raises(self):
        config = ChartConfig(type="line", data={})
        config.type = "invalid_type_xyz"  # Bypass Pydantic validation
        with pytest.raises(ChartError, match="Unknown chart type"):
            _build_figure(config)

    def test_chart_error_inherits_exception(self):
        err = ChartError("Test error")
        assert isinstance(err, Exception)
        assert str(err) == "Test error"


class TestLineChart:
    def test_simple_line_chart(self):
        config = ChartConfig(type="line", data={"x": [1, 2, 3], "y": [4, 5, 6]})
        fig = _create_line_chart(config)
        assert len(fig.data) == 1

    def test_line_chart_with_series(self):
        config = ChartConfig(
            type="line",
            data={"x": [[1, 2], [2, 3]], "y": [[4, 5], [5, 6]], "names": ["A", "B"]},
        )
        fig = _create_line_chart(config)
        assert len(fig.data) == 2

    def test_line_chart_no_x(self):
        config = ChartConfig(type="line", data={"y": [1, 2, 3]})
        fig = _create_line_chart(config)
        assert len(fig.data) == 1

    def test_line_chart_no_y(self):
        config = ChartConfig(type="line", data={"x": [1, 2, 3]})
        fig = _create_line_chart(config)
        assert len(fig.data) == 1

    def test_line_chart_values_key(self):
        config = ChartConfig(type="line", data={"values": [1, 2, 3]})
        fig = _create_line_chart(config)
        assert len(fig.data) == 1


class TestBarChart:
    def test_simple_bar_chart(self):
        config = ChartConfig(type="bar", data={"labels": ["A", "B"], "values": [10, 20]})
        fig = _create_bar_chart(config)
        assert len(fig.data) == 1

    def test_bar_chart_with_series(self):
        config = ChartConfig(
            type="bar",
            data={"labels": ["A", "B"], "y": [[10, 15], [20, 25]], "names": ["Set1", "Set2"]},
        )
        fig = _create_bar_chart(config)
        assert len(fig.data) == 2

    def test_bar_chart_values_key(self):
        config = ChartConfig(type="bar", data={"values": [10, 20, 30]})
        fig = _create_bar_chart(config)
        assert len(fig.data) == 1


class TestScatterChart:
    def test_simple_scatter(self):
        config = ChartConfig(type="scatter", data={"x": [1, 2, 3], "y": [4, 5, 6]})
        fig = _create_scatter_chart(config)
        assert len(fig.data) == 1

    def test_scatter_with_series(self):
        config = ChartConfig(
            type="scatter",
            data={"x": [[1, 2], [3, 4]], "y": [[4, 5], [6, 7]], "names": ["A", "B"]},
        )
        fig = _create_scatter_chart(config)
        assert len(fig.data) == 2

    def test_scatter_empty(self):
        config = ChartConfig(type="scatter", data={})
        fig = _create_scatter_chart(config)
        assert len(fig.data) == 1


class TestPieChart:
    def test_pie_chart(self):
        config = ChartConfig(type="pie", data={"labels": ["A", "B", "C"], "values": [30, 40, 30]})
        fig = _create_pie_chart(config)
        assert len(fig.data) == 1

    def test_pie_chart_names_key(self):
        config = ChartConfig(type="pie", data={"names": ["A", "B"], "values": [10, 20]})
        fig = _create_pie_chart(config)
        assert len(fig.data) == 1

    def test_pie_chart_y_key(self):
        config = ChartConfig(type="pie", data={"labels": ["A"], "y": [100]})
        fig = _create_pie_chart(config)
        assert len(fig.data) == 1


class TestAreaChart:
    def test_simple_area(self):
        config = ChartConfig(type="area", data={"x": [1, 2, 3], "y": [4, 5, 6]})
        fig = _create_area_chart(config)
        assert len(fig.data) == 1

    def test_area_with_series(self):
        config = ChartConfig(
            type="area",
            data={"x": [1, 2, 3], "y": [[4, 5], [5, 6]], "names": ["A", "B"]},
        )
        fig = _create_area_chart(config)
        assert len(fig.data) == 2

    def test_area_values_key(self):
        config = ChartConfig(type="area", data={"values": [1, 2, 3]})
        fig = _create_area_chart(config)
        assert len(fig.data) == 1


class TestHistogramChart:
    def test_histogram(self):
        config = ChartConfig(type="histogram", data={"x": [1, 2, 2, 3, 3, 3, 4]})
        fig = _create_histogram_chart(config)
        assert len(fig.data) == 1

    def test_histogram_values_key(self):
        config = ChartConfig(type="histogram", data={"values": [1, 2, 3, 4, 5]})
        fig = _create_histogram_chart(config)
        assert len(fig.data) == 1

    def test_histogram_with_bins(self):
        config = ChartConfig(type="histogram", data={"x": [1, 2, 3]}, options={"bins": 5})
        fig = _create_histogram_chart(config)
        assert len(fig.data) == 1


class TestBoxChart:
    def test_simple_box(self):
        config = ChartConfig(type="box", data={"y": [1, 2, 3, 4, 5]})
        fig = _create_box_chart(config)
        assert len(fig.data) == 1

    def test_box_with_x(self):
        config = ChartConfig(type="box", data={"x": ["A", "B"], "y": [1, 2]})
        fig = _create_box_chart(config)
        assert len(fig.data) == 1

    def test_box_with_series(self):
        config = ChartConfig(
            type="box",
            data={"y": [[1, 2, 3], [4, 5, 6]], "names": ["Group A", "Group B"]},
        )
        fig = _create_box_chart(config)
        assert len(fig.data) == 2

    def test_box_with_x_series(self):
        config = ChartConfig(
            type="box",
            data={"x": [["A", "B"], ["C", "D"]], "names": ["Group A", "Group B"]},
        )
        fig = _create_box_chart(config)
        assert len(fig.data) == 2


class TestHeatmapChart:
    def test_heatmap(self):
        config = ChartConfig(type="heatmap", data={"z": [[1, 2], [3, 4]]})
        fig = _create_heatmap_chart(config)
        assert len(fig.data) == 1

    def test_heatmap_with_labels(self):
        config = ChartConfig(
            type="heatmap",
            data={"z": [[1, 2], [3, 4]], "x_labels": ["A", "B"], "y_labels": ["X", "Y"]},
        )
        fig = _create_heatmap_chart(config)
        assert len(fig.data) == 1

    def test_heatmap_values_key(self):
        config = ChartConfig(type="heatmap", data={"values": [[1, 2]]})
        fig = _create_heatmap_chart(config)
        assert len(fig.data) == 1

    def test_heatmap_matrix_key(self):
        config = ChartConfig(type="heatmap", data={"matrix": [[1, 2], [3, 4]]})
        fig = _create_heatmap_chart(config)
        assert len(fig.data) == 1


class TestTreemapChart:
    def test_treemap(self):
        config = ChartConfig(
            type="treemap",
            data={"labels": ["A", "B", "C"], "values": [10, 20, 30]},
        )
        fig = _create_treemap_chart(config)
        assert len(fig.data) == 1

    def test_treemap_with_parents(self):
        config = ChartConfig(
            type="treemap",
            data={"labels": ["A", "B", "C"], "values": [10, 20, 30], "parents": ["", "A", "A"]},
        )
        fig = _create_treemap_chart(config)
        assert len(fig.data) == 1

    def test_treemap_names_key(self):
        config = ChartConfig(
            type="treemap",
            data={"names": ["A", "B"], "values": [10, 20]},
        )
        fig = _create_treemap_chart(config)
        assert len(fig.data) == 1


class TestSunburstChart:
    def test_sunburst(self):
        config = ChartConfig(
            type="sunburst",
            data={"labels": ["A", "B", "C"], "values": [10, 20, 30]},
        )
        fig = _create_sunburst_chart(config)
        assert len(fig.data) == 1

    def test_sunburst_with_parents(self):
        config = ChartConfig(
            type="sunburst",
            data={"labels": ["A", "B", "C"], "values": [10, 20, 30], "parents": ["", "A", "A"]},
        )
        fig = _create_sunburst_chart(config)
        assert len(fig.data) == 1


class TestFunnelChart:
    def test_funnel(self):
        config = ChartConfig(
            type="funnel",
            data={"stages": ["Lead", "Qualified", "Closed"], "values": [100, 50, 10]},
        )
        fig = _create_funnel_chart(config)
        assert len(fig.data) == 1

    def test_funnel_labels_key(self):
        config = ChartConfig(
            type="funnel",
            data={"labels": ["A", "B"], "values": [10, 20]},
        )
        fig = _create_funnel_chart(config)
        assert len(fig.data) == 1

    def test_funnel_y_key(self):
        config = ChartConfig(
            type="funnel",
            data={"labels": ["A", "B"], "y": [10, 20]},
        )
        fig = _create_funnel_chart(config)
        assert len(fig.data) == 1


class TestGaugeChart:
    def test_gauge(self):
        config = ChartConfig(type="gauge", data={"value": 75})
        fig = _create_gauge_chart(config)
        assert len(fig.data) == 1

    def test_gauge_with_title(self):
        config = ChartConfig(type="gauge", title="Performance", data={"value": 75})
        fig = _create_gauge_chart(config)
        assert len(fig.data) == 1

    def test_gauge_with_range(self):
        config = ChartConfig(type="gauge", data={"value": 75, "min": 0, "max": 200})
        fig = _create_gauge_chart(config)
        assert len(fig.data) == 1

    def test_gauge_with_thresholds(self):
        config = ChartConfig(
            type="gauge",
            data={
                "value": 75,
                "thresholds": {
                    "steps": [
                        {"range": [0, 50], "color": "green"},
                        {"range": [50, 100], "color": "red"},
                    ]
                },
            },
        )
        fig = _create_gauge_chart(config)
        assert len(fig.data) == 1


class TestIndicatorChart:
    def test_indicator(self):
        config = ChartConfig(type="indicator", data={"value": 42})
        fig = _create_indicator_chart(config)
        assert len(fig.data) == 1

    def test_indicator_with_delta(self):
        config = ChartConfig(type="indicator", data={"value": 42, "delta": 10})
        fig = _create_indicator_chart(config)
        assert len(fig.data) == 1

    def test_indicator_with_title(self):
        config = ChartConfig(type="indicator", title="Revenue", data={"value": 1000})
        fig = _create_indicator_chart(config)
        assert len(fig.data) == 1


class TestBubbleChart:
    def test_bubble(self):
        config = ChartConfig(type="bubble", data={"x": [1, 2, 3], "y": [4, 5, 6]})
        fig = _create_bubble_chart(config)
        assert len(fig.data) == 1

    def test_bubble_with_size(self):
        config = ChartConfig(type="bubble", data={"x": [1, 2], "y": [3, 4], "size": [10, 20]})
        fig = _create_bubble_chart(config)
        assert len(fig.data) == 1

    def test_bubble_with_colors(self):
        config = ChartConfig(
            type="bubble", data={"x": [1, 2], "y": [3, 4], "colors": ["red", "blue"]}
        )
        fig = _create_bubble_chart(config)
        assert len(fig.data) == 1


class TestBuildFigure:
    def test_build_figure_applies_title(self):
        config = ChartConfig(type="line", title="My Chart", data={"x": [1], "y": [1]})
        fig = _build_figure(config)
        assert fig.layout.title.text == "My Chart"

    def test_build_figure_applies_labels(self):
        config = ChartConfig(
            type="bar",
            title="Test",
            x_label="X",
            y_label="Y",
            data={"labels": ["A"], "values": [1]},
        )
        fig = _build_figure(config)
        assert fig.layout.xaxis.title.text == "X"
        assert fig.layout.yaxis.title.text == "Y"

    def test_build_figure_applies_dimensions(self):
        config = ChartConfig(
            type="line", data={"x": [1], "y": [1]}, options={"width": 1200, "height": 800}
        )
        fig = _build_figure(config)
        assert fig.layout.width == 1200
        assert fig.layout.height == 800

    def test_build_figure_applies_colors(self):
        config = ChartConfig(
            type="bar",
            data={"labels": ["A", "B"], "values": [10, 20]},
            options={"colors": ["red", "blue"]},
        )
        fig = _build_figure(config)
        assert fig.data[0].marker.color == "red"

    def test_build_figure_template(self):
        config = ChartConfig(
            type="line", data={"x": [1], "y": [1]}, options={"template": "plotly_white"}
        )
        fig = _build_figure(config)
        assert fig.layout.template is not None

    def test_build_figure_show_legend(self):
        config = ChartConfig(type="line", data={"x": [1], "y": [1]}, options={"show_legend": False})
        fig = _build_figure(config)
        assert fig.layout.showlegend is False


class TestCreateChart:
    def test_create_chart_returns_html(self):
        config = ChartConfig(type="line", data={"x": [1, 2, 3], "y": [4, 5, 6]})
        result = create_chart(config)
        assert isinstance(result, str)
        assert "<html" in result
        assert "plotly" in result.lower()

    def test_create_chart_bar(self):
        config = ChartConfig(type="bar", data={"labels": ["A", "B"], "values": [10, 20]})
        result = create_chart(config)
        assert "<html" in result

    def test_create_chart_pie(self):
        config = ChartConfig(type="pie", data={"labels": ["A"], "values": [100]})
        result = create_chart(config)
        assert "<html" in result


class TestCreateChartImageBytes:
    @patch("web_mcp.charts.generator._build_figure")
    def test_create_chart_image_bytes(self, mock_build):
        mock_fig = MagicMock()
        mock_fig.to_image.return_value = b"\x89PNG\r\n\x1a\n"
        mock_build.return_value = mock_fig

        config = ChartConfig(type="line", data={"x": [1], "y": [1]})
        result = create_chart_image_bytes(config, format="png", width=400, height=300)
        assert isinstance(result, bytes)
        mock_fig.update_layout.assert_called_once_with(width=400, height=300)
        mock_fig.to_image.assert_called_once_with(format="png", engine="kaleido")

    @patch("web_mcp.charts.generator._build_figure")
    def test_create_chart_image_bytes_jpeg(self, mock_build):
        mock_fig = MagicMock()
        mock_fig.to_image.return_value = b"jpeg data"
        mock_build.return_value = mock_fig

        config = ChartConfig(type="bar", data={"labels": ["A"], "values": [1]})
        result = create_chart_image_bytes(config, format="jpeg")
        assert b"jpeg data" in result

    @patch("web_mcp.charts.generator._build_figure")
    @patch("web_mcp.charts.generator._ensure_chrome")
    def test_create_chart_image_bytes_retries_chrome(self, mock_ensure, mock_build):
        mock_fig = MagicMock()
        mock_fig.to_image.side_effect = [
            RuntimeError("Chrome not found"),
            b"retried image data",
        ]
        mock_ensure.return_value = True
        mock_build.return_value = mock_fig

        config = ChartConfig(type="line", data={"x": [1], "y": [1]})
        result = create_chart_image_bytes(config)
        assert result == b"retried image data"
        assert mock_ensure.call_count == 1

    @patch("web_mcp.charts.generator._build_figure")
    @patch("web_mcp.charts.generator._ensure_chrome")
    def test_create_chart_image_bytes_chrome_failure_raises(self, mock_ensure, mock_build):
        mock_fig = MagicMock()
        mock_fig.to_image.side_effect = RuntimeError("Chrome not found")
        mock_ensure.return_value = False
        mock_build.return_value = mock_fig

        config = ChartConfig(type="line", data={"x": [1], "y": [1]})
        with pytest.raises(ChartError, match="Chrome"):
            create_chart_image_bytes(config)

    @patch("web_mcp.charts.generator._build_figure")
    def test_create_chart_image_bytes_other_runtime_error(self, mock_build):
        mock_fig = MagicMock()
        mock_fig.to_image.side_effect = RuntimeError("Some other error")
        mock_build.return_value = mock_fig

        config = ChartConfig(type="line", data={"x": [1], "y": [1]})
        with pytest.raises(RuntimeError, match="Some other error"):
            create_chart_image_bytes(config)


class TestCreateChartImage:
    @patch("web_mcp.charts.generator.create_chart_image_bytes")
    def test_create_chart_image_returns_data_url(self, mock_bytes):
        mock_bytes.return_value = b"\x89PNG"
        config = ChartConfig(type="line", data={"x": [1], "y": [1]})
        result = create_chart_image(config)
        assert result.startswith("data:image/png;base64,")

    @patch("web_mcp.charts.generator.create_chart_image_bytes")
    def test_create_chart_image_jpeg(self, mock_bytes):
        mock_bytes.return_value = b"jpeg"
        config = ChartConfig(type="bar", data={"labels": ["A"], "values": [1]})
        result = create_chart_image(config, format="jpeg")
        assert result.startswith("data:image/jpeg;base64,")

    @patch("web_mcp.charts.generator.create_chart_image_bytes")
    def test_create_chart_image_passes_dimensions(self, mock_bytes):
        mock_bytes.return_value = b"data"
        config = ChartConfig(type="line", data={"x": [1], "y": [1]})
        create_chart_image(config, format="png", width=1024, height=768)
        mock_bytes.assert_called_once_with(config, "png", 1024, 768)


class TestEnsureChrome:
    def test_ensure_chrome_success(self, monkeypatch):
        import sys
        from types import ModuleType
        from unittest.mock import MagicMock

        mock_kaleido = ModuleType("kaleido")
        mock_kaleido.get_chrome_sync = MagicMock(return_value="/usr/bin/chrome")
        monkeypatch.setitem(sys.modules, "kaleido", mock_kaleido)

        # Reset the _chrome_installed flag to test the function
        import web_mcp.charts.generator as gen
        from web_mcp.charts.generator import _ensure_chrome

        gen._chrome_installed = False

        result = _ensure_chrome()
        assert result is True

    def test_ensure_chrome_failure(self, monkeypatch):
        import sys
        from types import ModuleType
        from unittest.mock import MagicMock

        mock_kaleido = ModuleType("kaleido")
        mock_kaleido.get_chrome_sync = MagicMock(side_effect=Exception("Not found"))
        monkeypatch.setitem(sys.modules, "kaleido", mock_kaleido)

        # Reset the _chrome_installed flag to test the function
        import web_mcp.charts.generator as gen
        from web_mcp.charts.generator import _ensure_chrome

        gen._chrome_installed = False

        result = _ensure_chrome()
        assert result is False
