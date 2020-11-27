from init_app import app

# TODO: Register callbacks in a better way...
from plot_utils import update_graph  # noqa
from page_layout import update_select_time_series  # noqa


if __name__ == "__main__":
    app.run_server(debug=True)
