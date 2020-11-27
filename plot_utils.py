from datetime import datetime

from dash.dependencies import Input, Output
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go
import pandas as pd

from init_app import app
from utils import compute_granularity, RAW_DPS_GRAN, get_client


@app.callback(
    Output("graph-ts", "figure"),
    [
        Input("select-ts", "value"),
        Input("time-filter", "children"),
        Input("agg-slider", "value"),
        Input("select-plot-resolution", "value"),
    ]
)
def update_graph(ts_xid, time_filter, show_raw_dps, n_points):
    if not ts_xid or not time_filter:
        raise PreventUpdate

    client = get_client()
    ts = client.time_series.retrieve(external_id=ts_xid)

    start, end = time_filter
    if start == end:
        end += 1  # At least 1 ms duration

    granularity, human_gran_txt = compute_granularity(start, end, show_raw_dps, n_points)
    if figure_shows_raw_dps(granularity):
        agg_gran_kw = dict(include_outside_points=True)
    else:
        agg_gran_kw = dict(aggregates=["average", "min", "max"], granularity=granularity)

    dps = client.datapoints.retrieve(external_id=ts_xid, start=start, end=end, **agg_gran_kw)
    datetime_index = pd.to_datetime(dps.timestamp, unit="ms")

    fig = go.Figure(layout=create_fig_layout(ts, human_gran_txt, datetime_index.size))
    if figure_shows_raw_dps(granularity):
        trace_kw = dict(y=dps.value, name="Raw", mode="lines+markers", showlegend=True)
    else:
        trace_kw = dict(y=dps.average, name="Average", mode="lines")
        add_min_max_area(fig, datetime_index, dps)

    add_main_line(fig, datetime_index, trace_kw)
    set_xaxis(fig, start, end)
    return fig


def figure_shows_raw_dps(granularity):
    return granularity == RAW_DPS_GRAN


def create_fig_layout(ts, human_gran_txt, n_points_plotted):
    return go.Layout(
        title=f"{ts.name} [{ts.external_id}]\nGranularity: {human_gran_txt}, drawn points: {n_points_plotted}",
        xaxis={"title": "Time"},
        yaxis={"title": f"Value [{ts.unit or 'N/A'}]"},
    )


def add_min_max_area(fig, datetime_index, dps):
    fig.add_traces(
        [
            go.Scatter(
                x=datetime_index,
                y=dps.min,
                fill=None,
                mode="lines",
                line=dict(width=0.5, color="rgba(0, 40, 100, 0.2)"),
                name="min",
                showlegend=False,
            ),
            go.Scatter(
                x=datetime_index,
                y=dps.max,
                fill="tonexty",  # fills area between min and max
                mode="lines",
                name="max",
                fillcolor="rgba(0,40,100,0.2)",
                line=dict(width=0.5, color="rgba(0, 40, 100, 0.2)"),
                showlegend=False,
            ),
        ]
    )


def add_main_line(fig, datetime_index, trace_kw):
    fig.add_trace(
        go.Scatter(
            x=datetime_index,
            **trace_kw,
            line=dict(width=0.75, color="rgb(0, 40, 100)"),
        )
    )


def set_xaxis(fig, start, end):
    # HACK to fix axes (dash tz problem...): Please don't ask about this (it"s so döööörty)
    start = 1000 * datetime.utcfromtimestamp(start / 1000).astimezone().timestamp()
    end = 1000 * datetime.utcfromtimestamp(end / 1000).astimezone().timestamp()
    fig.update_xaxes(range=[start, end])
