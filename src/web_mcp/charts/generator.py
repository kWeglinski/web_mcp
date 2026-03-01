import plotly.graph_objects as go
import plotly.express as px
from typing import Any, Literal
from pydantic import BaseModel, Field

CHART_TYPES = Literal[
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


class ChartConfig(BaseModel):
    type: CHART_TYPES = Field(description="Type of chart to create")
    title: str = Field(default="", description="Chart title")
    x_label: str = Field(default="", description="X-axis label")
    y_label: str = Field(default="", description="Y-axis label")
    data: dict[str, Any] = Field(description="Chart data as JSON object")
    options: dict[str, Any] = Field(default_factory=dict, description="Additional chart options")


class ChartError(Exception):
    pass


def _extract_data_arrays(data: dict[str, Any]) -> dict[str, list]:
    result = {}
    for key, value in data.items():
        if isinstance(value, list):
            result[key] = value
        elif isinstance(value, dict):
            nested = _extract_data_arrays(value)
            for nk, nv in nested.items():
                result[f"{key}_{nk}"] = nv
        else:
            result[key] = [value]
    return result


def _create_line_chart(config: ChartConfig) -> go.Figure:
    data = config.data
    x = data.get("x", data.get("labels", list(range(len(data.get("y", data.get("values", [])))))))
    y = data.get("y", data.get("values", []))
    fig = go.Figure()
    if isinstance(y[0], list) if y else False:
        for i, y_series in enumerate(y):
            name = data.get("names", [f"Series {i+1}"])[i] if data.get("names") else f"Series {i+1}"
            fig.add_trace(go.Scatter(x=x, y=y_series, mode="lines+markers", name=name))
    else:
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers"))
    return fig


def _create_bar_chart(config: ChartConfig) -> go.Figure:
    data = config.data
    x = data.get("x", data.get("labels", []))
    y = data.get("y", data.get("values", []))
    fig = go.Figure()
    if y and isinstance(y[0], list):
        for i, y_series in enumerate(y):
            name = data.get("names", [f"Series {i+1}"])[i] if data.get("names") else f"Series {i+1}"
            fig.add_trace(go.Bar(x=x, y=y_series, name=name))
    else:
        fig.add_trace(go.Bar(x=x, y=y))
    return fig


def _create_scatter_chart(config: ChartConfig) -> go.Figure:
    data = config.data
    x = data.get("x", [])
    y = data.get("y", [])
    fig = go.Figure()
    if y and isinstance(y[0], list):
        for i, y_series in enumerate(y):
            name = data.get("names", [f"Series {i+1}"])[i] if data.get("names") else f"Series {i+1}"
            x_series = x[i] if isinstance(x[0], list) else x
            fig.add_trace(go.Scatter(x=x_series, y=y_series, mode="markers", name=name))
    else:
        fig.add_trace(go.Scatter(x=x, y=y, mode="markers"))
    return fig


def _create_pie_chart(config: ChartConfig) -> go.Figure:
    data = config.data
    labels = data.get("labels", data.get("names", []))
    values = data.get("values", data.get("y", []))
    fig = go.Figure(go.Pie(labels=labels, values=values))
    return fig


def _create_area_chart(config: ChartConfig) -> go.Figure:
    data = config.data
    x = data.get("x", list(range(len(data.get("y", data.get("values", []))))))
    y = data.get("y", data.get("values", []))
    fig = go.Figure()
    if y and isinstance(y[0], list):
        for i, y_series in enumerate(y):
            name = data.get("names", [f"Series {i+1}"])[i] if data.get("names") else f"Series {i+1}"
            fig.add_trace(go.Scatter(x=x, y=y_series, mode="lines", stackgroup="one", name=name))
    else:
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", stackgroup="one"))
    return fig


def _create_histogram_chart(config: ChartConfig) -> go.Figure:
    data = config.data
    x = data.get("x", data.get("values", []))
    fig = go.Figure(go.Histogram(x=x, nbinsx=data.get("bins", 10)))
    return fig


def _create_box_chart(config: ChartConfig) -> go.Figure:
    data = config.data
    x = data.get("x", None)
    y = data.get("y", data.get("values", []))
    fig = go.Figure()
    if x and isinstance(x[0], list):
        for i, x_series in enumerate(x):
            name = data.get("names", [f"Group {i+1}"])[i] if data.get("names") else f"Group {i+1}"
            fig.add_trace(go.Box(y=x_series, name=name))
    elif isinstance(y[0], list) if y else False:
        for i, y_series in enumerate(y):
            name = data.get("names", [f"Group {i+1}"])[i] if data.get("names") else f"Group {i+1}"
            fig.add_trace(go.Box(y=y_series, name=name))
    else:
        fig.add_trace(go.Box(y=y))
    return fig


def _create_heatmap_chart(config: ChartConfig) -> go.Figure:
    data = config.data
    z = data.get("z", data.get("values", data.get("matrix", [])))
    x = data.get("x", data.get("x_labels", None))
    y = data.get("y", data.get("y_labels", None))
    fig = go.Figure(go.Heatmap(z=z, x=x, y=y))
    return fig


def _create_treemap_chart(config: ChartConfig) -> go.Figure:
    data = config.data
    labels = data.get("labels", data.get("names", []))
    values = data.get("values", [])
    parents = data.get("parents", [""] * len(labels))
    fig = go.Figure(go.Treemap(labels=labels, values=values, parents=parents))
    return fig


def _create_sunburst_chart(config: ChartConfig) -> go.Figure:
    data = config.data
    labels = data.get("labels", data.get("names", []))
    values = data.get("values", [])
    parents = data.get("parents", [""] * len(labels))
    fig = go.Figure(go.Sunburst(labels=labels, values=values, parents=parents))
    return fig


def _create_funnel_chart(config: ChartConfig) -> go.Figure:
    data = config.data
    labels = data.get("labels", data.get("names", data.get("stages", [])))
    values = data.get("values", data.get("y", []))
    fig = go.Figure(go.Funnel(y=labels, x=values))
    return fig


def _create_gauge_chart(config: ChartConfig) -> go.Figure:
    data = config.data
    value = data.get("value", data.get("values", 0))
    title = data.get("title", config.title or "Gauge")
    max_val = data.get("max", 100)
    min_val = data.get("min", 0)
    thresholds = data.get("thresholds", {"steps": []})
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title},
        gauge={
            "axis": {"range": [min_val, max_val]},
            "steps": thresholds.get("steps", [
                {"range": [min_val, max_val * 0.5], "color": "lightgray"},
                {"range": [max_val * 0.5, max_val * 0.8], "color": "gray"},
            ]),
            "threshold": {
                "line": {"color": "red", "width": 4},
                "thickness": 0.75,
                "value": data.get("threshold", max_val * 0.9),
            },
        },
    ))
    return fig


def _create_indicator_chart(config: ChartConfig) -> go.Figure:
    data = config.data
    value = data.get("value", data.get("values", 0))
    title = data.get("title", config.title or "Indicator")
    mode = data.get("mode", "number+delta")
    delta = data.get("delta", None)
    
    indicator_mode = mode
    if delta is not None:
        indicator_mode = "number+delta"
    
    fig = go.Figure(go.Indicator(
        mode=indicator_mode,
        value=value,
        title={"text": title},
        delta={"reference": delta} if delta is not None else None,
    ))
    return fig


def _create_bubble_chart(config: ChartConfig) -> go.Figure:
    data = config.data
    x = data.get("x", [])
    y = data.get("y", [])
    size = data.get("size", data.get("sizes", [20] * len(x)))
    color = data.get("color", data.get("colors", None))
    fig = go.Figure(go.Scatter(
        x=x,
        y=y,
        mode="markers",
        marker={"size": size, "color": color, "sizemode": "diameter"},
    ))
    return fig


CHART_BUILDERS = {
    "line": _create_line_chart,
    "bar": _create_bar_chart,
    "scatter": _create_scatter_chart,
    "pie": _create_pie_chart,
    "area": _create_area_chart,
    "histogram": _create_histogram_chart,
    "box": _create_box_chart,
    "heatmap": _create_heatmap_chart,
    "treemap": _create_treemap_chart,
    "sunburst": _create_sunburst_chart,
    "funnel": _create_funnel_chart,
    "gauge": _create_gauge_chart,
    "indicator": _create_indicator_chart,
    "bubble": _create_bubble_chart,
}


def create_chart(config: ChartConfig) -> str:
    chart_type = config.type
    if chart_type not in CHART_BUILDERS:
        raise ChartError(f"Unknown chart type: {chart_type}. Valid types: {list(CHART_BUILDERS.keys())}")
    
    builder = CHART_BUILDERS[chart_type]
    fig = builder(config)
    
    if config.title:
        fig.update_layout(title=config.title)
    if config.x_label:
        fig.update_layout(xaxis_title=config.x_label)
    if config.y_label:
        fig.update_layout(yaxis_title=config.y_label)
    
    options = config.options
    if options:
        if "width" in options or "height" in options:
            fig.update_layout(
                width=options.get("width"),
                height=options.get("height"),
            )
        if "template" in options:
            fig.update_layout(template=options["template"])
        if "show_legend" in options:
            fig.update_layout(showlegend=options["show_legend"])
        if "colors" in options:
            colors = options["colors"]
            if isinstance(colors, list):
                for i, trace in enumerate(fig.data):
                    if i < len(colors):
                        if hasattr(trace, "marker"):
                            trace.marker.color = colors[i]
                        elif hasattr(trace, "line"):
                            trace.line.color = colors[i]
    
    return fig.to_html(
        include_plotlyjs="cdn",
        full_html=True,
        config={"responsive": True, "displayModeBar": True, "scrollZoom": True},
    )
