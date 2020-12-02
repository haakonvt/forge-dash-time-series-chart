from dacite import from_dict
from dataclasses import dataclass, asdict as dataclass_to_dict
import json
from itertools import cycle
from datetime import datetime

from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from seaborn import color_palette

from init_app import app
from utils import compute_granularity, RAW_DPS_GRAN, get_client


MAX_SIMULTANEOUS_PLOTS = 5


@app.callback(
    [Output("graph-ts", "figure"), Output("color-lookup", "children")],
    [
        Input("select-ts", "value"),
        Input("time-filter", "children"),
        Input("agg-slider", "value"),
        Input("select-plot-resolution", "value"),
    ],
    [State("color-lookup", "children")]
)
def update_graph(ts_xid_lst, time_filter, show_raw_dps, n_points, color_lookup):
    # Tip: Dash ~NOUPDATE
    if not ts_xid_lst or not time_filter:
        raise PreventUpdate

    start, end = time_filter
    if start == end:
        end += 1  # At least 1 ms duration

    granularity, human_granularity = compute_granularity(start, end, show_raw_dps, n_points)
    if figure_shows_raw_dps(granularity):
        agg_gran_kw = dict(include_outside_points=True)
    else:
        agg_gran_kw = dict(aggregates=["average", "min", "max"], granularity=granularity)

    fig = go.Figure(layout=create_fig_layout(ts_xid_lst, granularity, human_granularity))

    tot_plots = len(ts_xid_lst)
    if tot_plots > MAX_SIMULTANEOUS_PLOTS:
        raise RuntimeError(f"Currently, {MAX_SIMULTANEOUS_PLOTS} is the maximum number of simultaneous plots")

    all_ts = get_client().time_series.retrieve_multiple(external_ids=ts_xid_lst)
    all_colors, color_lookup = get_all_graph_colors(all_ts, json.loads(color_lookup or '{}'))
    for plot_n, (ts, color) in enumerate(zip(all_ts, all_colors), 1):
        _add_single_graph(fig, ts, start, end, agg_gran_kw, granularity, color, plot_n)

    start_offset, end_offset = compute_start_end_tz_offset(fig, start, end)
    dom_start = compute_xstart_position(tot_plots)
    fig.update_xaxes(range=[start_offset, end_offset], domain=[dom_start, 1])
    add_all_yaxes(fig, all_ts, all_colors)
    fig.update_layout(hovermode="x")  # x is just specific mode
    return fig, json.dumps(color_lookup)


def compute_xstart_position(n):
    return 0 if n <= 1 else 0.03 * n


def add_all_yaxes(fig, all_ts, all_colors):
    yaxis_dct = dict(
        yaxis=dict(
            showline=True,
            showgrid=False,
            position=compute_xstart_position(1),
            titlefont={"color": all_colors[0].line.as_dash_color()},
            tickfont={"color": all_colors[0].line.as_dash_color()},
        )
    )
    for n, color in enumerate(all_colors[1:], 2):
        yaxis_dct[f"yaxis{n}"] = dict(
            showline=True,
            showgrid=False,
            titlefont={"color": color.line.as_dash_color()},
            tickfont={"color": color.line.as_dash_color()},
            position=compute_xstart_position(n),
            **dict(anchor="free", overlaying="y", side="left"),
        )
    fig.update_layout(**yaxis_dct)


def compute_start_end_tz_offset(fig, start, end):
    # HACK to fix axes (dash tz problem...): Please don't ask about this (it's so döööörty)
    start = 1000 * datetime.utcfromtimestamp(start / 1000).astimezone().timestamp()
    end = 1000 * datetime.utcfromtimestamp(end / 1000).astimezone().timestamp()
    return start, end


def _add_single_graph(fig, ts, start, end, agg_gran_kw, granularity, color, plot_n):
    dps = get_client().datapoints.retrieve(external_id=ts.external_id, start=start, end=end, **agg_gran_kw)
    datetime_index = pd.to_datetime(dps.timestamp, unit="ms")

    if figure_shows_raw_dps(granularity):
        trace_kw = dict(y=dps.value, name=ts.name, mode="lines+markers", showlegend=True)
    else:
        trace_kw = dict(y=dps.average, name=ts.name, mode="lines")
        add_min_max_area(fig, datetime_index, dps, color, plot_n)

    add_main_line(fig, datetime_index, trace_kw, color.line, plot_n)


def figure_shows_raw_dps(granularity):
    return granularity == RAW_DPS_GRAN


def create_fig_layout(ts_xid_lst, granularity, human_granularity):
    aggregate = "Not used" if figure_shows_raw_dps(granularity) else "Average"
    title = f"Aggregate: {aggregate}. Granularity: {human_granularity}"
    if len(ts_xid_lst) == 1:
        ts = get_client().time_series.retrieve(external_id=ts_xid_lst[0])
        title = f"{ts.name} [{ts.external_id}]. {title}"
    return go.Layout(
        title=title,
        xaxis={"title": "Time"},
    )


def add_min_max_area(fig, datetime_index, dps, color, plot_n):
    alpha = 1.2 / (plot_n + 1)  # Magic formula to make stacked min-max-areas equally weighted
    fillcolor = color.fillcolor.set_alpha(alpha).as_dash_color(alpha=True)
    fig.add_traces(
        [
            go.Scatter(
                x=datetime_index,
                y=dps.min,
                fill=None,
                mode="lines",
                line=dict(width=0, color=color.line.as_dash_color()),
                name="Min",
                showlegend=False,
                yaxis=f"y{plot_n}",
            ),
            go.Scatter(
                x=datetime_index,
                y=dps.max,
                fill="tonexty",  # fills area between min and max
                mode="lines",
                name="Max",
                fillcolor=fillcolor,
                line=dict(width=0, color=color.line.as_dash_color()),
                showlegend=False,
                yaxis=f"y{plot_n}",
            ),
        ]
    )


def add_main_line(fig, datetime_index, trace_kw, color, plot_n):
    fig.add_trace(
        go.Scatter(
            x=datetime_index,
            line=dict(width=1.75, color=color.as_dash_color()),
            yaxis=f"y{plot_n}",
            **trace_kw,
        )
    )


@dataclass(frozen=True)
class RGBA:
    r: float
    g: float
    b: float
    a: float = 1.0  # alpha/opacity [0, 1]

    def __post_init__(self):
        # Frozen makes post init setattrs a bit ugly:
        object.__setattr__(self, "rgb", (self.r, self.g, self.b))
        object.__setattr__(self, "rgba", self.rgb + (self.a,))
        assert all(0 <= v <= 1 for v in self.rgba), (
            f"[R,G,B,A] must be 0 <= value <= 1, not '{self.rgba}'"
        )

    def as_dash_color(self, *, alpha=False):
        var = f"rgb{'a' if alpha else ''}"
        return f"{var}{getattr(self, var)}"

    def as_dash_light_color(self):
        delta_max = 1 - max(self.rgb)
        return f"rgba({self.r + delta_max},{self.g + delta_max},{self.b + delta_max},{self.a})"

    def set_alpha(self, alpha):
        object.__setattr__(self, "a", alpha)
        self.__post_init__()
        return self  # To allow chained expr


@dataclass
class PlotColors:
    fillcolor: RGBA
    line: RGBA


# We use Seaborn color palette "Paired" to get good background+foreground colors:
COLORS = cycle(color_palette("Paired"))


def get_all_graph_colors(all_ts, color_lookup):
    def _color_dct_update(ts, key_attr="external_id"):
        key = getattr(ts, key_attr)
        if (color := color_lookup.get(key)) is None:
            # If you are NOT using color palette "Paired", change to:
            # rgb = RGBA(*next(COLORS))
            # new_color = PlotColors(rgb, rgb)
            new_color = PlotColors(RGBA(*next(COLORS)), RGBA(*next(COLORS)))
            color_lookup[key] = dataclass_to_dict(new_color)
            return new_color
        return from_dict(data_class=PlotColors, data=color)

    colors = list(map(_color_dct_update, all_ts))
    return colors, color_lookup
