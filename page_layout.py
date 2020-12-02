from dash import callback_context
from dash.dependencies import Input, Output
from dash.exceptions import PreventUpdate
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
import pandas as pd

from init_app import app
from utils import get_client, pandas_ts_to_unix_ms, SHOW_RAW_DPS_DEFAULT


@app.callback(
    Output("select-ts", "options"),
    [Input("select-dates", "start_date")]
)
def update_select_time_series(_):  # TODO: How to get rid of input?
    client = get_client()
    # Single TS (good for test purposes):
    # ts_list = [client.time_series.retrieve(id=6879658344978017)]

    # Multiple time series:
    ts_list = client.time_series.list(is_string=False, limit=50)
    ts_list.sort(key=lambda ts: ts.name or "")
    options = [
        {"label": name, "value": val}
        for name, val in zip((t.name for t in ts_list), (t.external_id for t in ts_list))
    ]
    return options


@app.callback(Output("time-filter", "children"),
              [Input("select-dates", "start_date"),
               Input("select-dates", "end_date"),
               Input("graph-ts", "relayoutData")])
def update_time_filter(start_date, end_date, relayout_data):
    start, end = None, None
    triggered = callback_context.triggered[0]["prop_id"]
    if triggered == "graph-ts.relayoutData" and relayout_data:
        if (start := relayout_data.get("xaxis.range[0]")):
            end = relayout_data["xaxis.range[1]"]
        elif "yaxis.range[0]" in relayout_data:
            raise PreventUpdate

    if not start or not end:
        start = pandas_ts_to_unix_ms(pd.Timestamp(start_date))
        end = pandas_ts_to_unix_ms((pd.Timestamp(end_date) + pd.Timedelta(1, unit="D")))

    if isinstance(start, str) or isinstance(end, str):
        start = pandas_ts_to_unix_ms(pd.Timestamp(start))
        end = pandas_ts_to_unix_ms(pd.Timestamp(end))
    return start, end


_agg_slider_marks = {
    0: "OFF", 20: "", 40: "", 60: "1h", 90: "", **{k*60: f"{k}h" for k in range(2, 13)}
}
inp_grp_raw_dps_slider = dbc.FormGroup(
    [
        dbc.InputGroupAddon("Turn off aggregation below: ", addon_type="prepend"),
        dcc.Slider(
            id="agg-slider", min=0, max=720, step=10, value=SHOW_RAW_DPS_DEFAULT,
            tooltip={}, marks=_agg_slider_marks
        ),
    ]
)

PLOT_RES_DEFAULT = 250
_plot_resolution_options = [
    {"label": "Extreme", "value": 750},
    {"label": "High", "value": 400},
    {"label": "Standard", "value": PLOT_RES_DEFAULT},
    {"label": "Low", "value": 100},
]
inp_grp_dps_resolution = dbc.FormGroup(
    [
        dbc.InputGroupAddon("Plot resolution: ", addon_type="prepend"),
        dbc.RadioItems(
            id="select-plot-resolution",
            options=_plot_resolution_options,
            value=PLOT_RES_DEFAULT,
            inline=True,
        ),
    ]
)


inp_grp_ts_selector = dbc.InputGroup(
    [
        dbc.InputGroupAddon("Time series: ", addon_type="prepend"),
        dcc.Dropdown(id="select-ts", options=[], multi=True, style={"width": "50vh"}),
    ]
)
# Set default time range to last week:
NOW_TS = pd.Timestamp("now")
TODAY = str(NOW_TS.date())
ONE_WEEK_AGO = str((NOW_TS - pd.Timedelta(1, unit="W")).date())

inp_grp_date_selector = dbc.InputGroup([
    dbc.InputGroupAddon("Date range: ", addon_type="prepend"),
    dcc.DatePickerRange(id="select-dates", start_date=ONE_WEEK_AGO, end_date=TODAY),
])

# Full app layout:
app.layout = html.Div([
    html.Div(id="time-filter", hidden=True),
    html.Div(id="color-lookup", hidden=True),  # Client side storage
    dbc.Card(
        [
            dbc.CardHeader(html.H6("Settings")),
            dbc.CardBody([
                dbc.Row([dbc.Col(inp_grp_ts_selector), dbc.Col(inp_grp_date_selector)]),
            ]),
            dbc.CardHeader(html.H6("Advanced settings")),
            dbc.CardBody([
                dbc.Row([dbc.Col(inp_grp_raw_dps_slider), dbc.Col(inp_grp_dps_resolution)]),
            ]),
        ]
    ),
    dbc.Card(
        [
            dbc.CardHeader(html.H6("Graph")),
            dbc.CardBody(dcc.Loading(dcc.Graph(id="graph-ts", figure={}))),
        ],
    )
])
