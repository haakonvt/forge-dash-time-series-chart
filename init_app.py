from dash import Dash
from dash_bootstrap_components.themes import BOOTSTRAP

# Make 'app' importable from various modules:
app = Dash(__name__, external_stylesheets=[BOOTSTRAP])
