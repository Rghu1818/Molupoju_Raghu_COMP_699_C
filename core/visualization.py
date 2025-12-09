import pandas as pd
import plotly.express as px


def line_timeseries(df: pd.DataFrame, x: str, y: str, title: str = "Timeseries"):
    if df is None or df.empty:
        return None
    fig = px.line(df, x=x, y=y, title=title)
    fig.update_layout(hovermode="x unified")
    return fig


def heatmap_from_grid(df: pd.DataFrame, row: str = "row", col: str = "col", value: str = "value", title: str = "Sensor Heatmap"):
    if df is None or df.empty:
        return None
    pivot = df.pivot(index=row, columns=col, values=value)
    fig = px.imshow(pivot, aspect="equal", color_continuous_scale="Viridis", origin="lower", title=title)
    return fig
