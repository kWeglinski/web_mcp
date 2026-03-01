# Charting Tool Implementation Plan

## Overview
Add a comprehensive charting tool to the web_mcp server that allows the model to create modern, interactive visualizations using Plotly.

## Requirements
- **Chart Types**: Comprehensive set including Line, Bar, Pie, Scatter, Area, Donut, Histogram, Box Plot, Heatmap, Radar, Bubble, Candlestick, Funnel, Treemap
- **Output Format**: Interactive HTML with embedded JavaScript (Plotly)
- **Aesthetics**: Modern, clean design with good defaults

## Implementation Plan

### 1. Add Dependencies
**File**: `pyproject.toml`

Add Plotly to dependencies:
```toml
"plotly>=5.18.0",
```

### 2. Create Charting Module
**File**: `src/web_mcp/charts/__init__.py`

Module initialization and exports.

**File**: `src/web_mcp/charts/generator.py`

Core chart generation logic with Plotly. This will include:
- A `ChartGenerator` class with methods for each chart type
- Modern theme configuration (clean colors, good typography, proper spacing)
- Data validation and error handling
- HTML template wrapper for consistent styling

**Chart Types to Implement**:
1. **Line Chart** - Time series, trends
2. **Bar Chart** - Categorical comparisons
3. **Pie Chart** - Proportions
4. **Donut Chart** - Modern pie variant
5. **Scatter Plot** - Correlations
6. **Area Chart** - Cumulative trends
7. **Histogram** - Distribution
8. **Box Plot** - Statistical summary
9. **Heatmap** - 2D data density
10. **Radar Chart** - Multi-dimensional comparison
11. **Bubble Chart** - 3-variable scatter
12. **Candlestick** - Financial data
13. **Funnel Chart** - Process stages
14. **Treemap** - Hierarchical proportions

### 3. Create MCP Tool Interface
**File**: `src/web_mcp/server.py`

Add a new tool `create_chart`:

```python
@mcp.tool()
async def create_chart(
    chart_type: str = Field(description="Type of chart: line, bar, pie, donut, scatter, area, histogram, box, heatmap, radar, bubble, candlestick, funnel, treemap"),
    data: dict = Field(description="Chart data in JSON format (structure varies by chart type)"),
    title: str = Field(default="", description="Chart title"),
    options: dict = Field(default={}, description="Additional styling options")
) -> str:
    """Create an interactive chart visualization.
    
    Returns HTML with embedded Plotly JavaScript for interactive charts
    with zoom, pan, hover tooltips, and export capabilities.
    """
```

### 4. Data Schema Design

Each chart type will accept a standardized data format:

**Line/Bar/Area/Scatter Charts**:
```json
{
  "x": ["Jan", "Feb", "Mar"],
  "y": [10, 20, 15],
  "series": "Series Name"  // optional for multi-series
}
```

**Pie/Donut Charts**:
```json
{
  "labels": ["Category A", "Category B", "Category C"],
  "values": [30, 40, 30]
}
```

**Histogram/Box Plot**:
```json
{
  "values": [1, 2, 3, 4, 5, ...],
  "bins": 20  // optional
}
```

**Heatmap**:
```json
{
  "z": [[1, 2, 3], [4, 5, 6]],
  "x": ["Col1", "Col2", "Col3"],
  "y": ["Row1", "Row2"]
}
```

**Radar Chart**:
```json
{
  "categories": ["Speed", "Reliability", "Cost"],
  "values": [80, 90, 70]
}
```

**Bubble Chart**:
```json
{
  "x": [1, 2, 3],
  "y": [10, 20, 15],
  "size": [100, 200, 150],
  "labels": ["A", "B", "C"]
}
```

**Candlestick**:
```json
{
  "dates": ["2024-01-01", "2024-01-02"],
  "open": [100, 105],
  "high": [110, 115],
  "low": [95, 100],
  "close": [105, 110]
}
```

**Funnel**:
```json
{
  "stages": ["Visits", "Signups", "Purchases"],
  "values": [1000, 500, 100]
}
```

**Treemap**:
```json
{
  "labels": ["Root", "Child1", "Child2"],
  "parents": ["", "Root", "Root"],
  "values": [0, 30, 70]
}
```

### 5. Modern Theme Configuration
**File**: `src/web_mcp/charts/theme.py`

Define a modern color palette and styling:
- Clean, minimal design
- Professional color palette (not too bright)
- Good contrast and readability
- Responsive layout
- Proper margins and spacing

### 6. HTML Template
**File**: `src/web_mcp/charts/template.py`

HTML wrapper that includes:
- Plotly.js CDN link
- Responsive container
- Dark/light mode support (optional)
- Export button (Plotly built-in)

### 7. Testing
**File**: `tests/test_charts.py`

Unit tests for:
- Each chart type generation
- Data validation
- Error handling
- HTML output format

### 8. Documentation
**File**: `docs/charting.md`

Comprehensive documentation including:
- Tool usage examples
- Data format for each chart type
- Styling options
- Best practices

## File Structure
```
src/web_mcp/
├── charts/
│   ├── __init__.py
│   ├── generator.py      # Chart generation logic
│   ├── theme.py          # Modern theme configuration
│   └── template.py       # HTML template wrapper
├── server.py             # Add create_chart tool
tests/
└── test_charts.py        # Chart tests
docs/
└── charting.md           # Charting documentation
```

## Implementation Steps

1. **Add plotly dependency** to `pyproject.toml`
2. **Create charts module structure** (`charts/__init__.py`, `charts/generator.py`, `charts/theme.py`, `charts/template.py`)
3. **Implement ChartGenerator class** with methods for all 14 chart types
4. **Create modern theme** with professional color palette
5. **Add create_chart tool** to `server.py`
6. **Write comprehensive tests** for all chart types
7. **Create documentation** with examples
8. **Test the integration** with the MCP server

## Example Usage

```python
# Line chart
create_chart(
    chart_type="line",
    data={"x": ["Jan", "Feb", "Mar"], "y": [10, 20, 15]},
    title="Monthly Sales"
)

# Pie chart
create_chart(
    chart_type="pie",
    data={"labels": ["A", "B", "C"], "values": [30, 40, 30]},
    title="Market Share"
)

# Multi-series line chart
create_chart(
    chart_type="line",
    data={
        "series": [
            {"name": "Product A", "x": ["Q1", "Q2", "Q3"], "y": [100, 150, 200]},
            {"name": "Product B", "x": ["Q1", "Q2", "Q3"], "y": [80, 120, 180]}
        ]
    },
    title="Quarterly Revenue"
)
```

## Benefits
- **Interactive**: Zoom, pan, hover tooltips
- **Modern**: Clean Plotly aesthetics
- **Comprehensive**: 14 chart types covering most use cases
- **Simple API**: Easy for models to generate correct data
- **Flexible**: Optional styling parameters for customization
- **Self-contained**: HTML output works standalone

## Notes
- Plotly.js is loaded from CDN (requires internet connection for viewing)
- Charts are responsive and work on mobile
- Built-in export to PNG/SVG via Plotly toolbar
- No server-side rendering needed - all client-side JavaScript
