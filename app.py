import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd

import methods

dataframes = methods.get_data(rebuild=False)

df1 = methods.nominations_per_bn(
    dataframes["mapsets"], dataframes["nominators"], proportional=False
)
df2 = methods.unique_mappers_nominated(
    dataframes["mapsets"], dataframes["nominators"], proportional=False, minimum_noms=0
)
df1 = df1.merge(df2, on=["user_id", "usernames"])
df2 = methods.unique_mappers_nominated(
    dataframes["mapsets"], dataframes["nominators"], proportional=True, minimum_noms=0
)
df = df1.merge(df2, on=["user_id", "usernames"])
unique_mappers_nominated_fig = px.scatter(
    data_frame=df,
    x="nominations",
    y="unique_mappers_x",
    color="unique_mappers_y",
    hover_data=["usernames"],
    trendline="lowess",
)

external_stylesheets = ["https://codepen.io/chriddyp/pen/bWLwgP.css"]

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

app.layout = html.Div(
    children=[
        html.H1(children="Beatmap Nominator Data Visualizations"),
        html.Div(children="""Data from Aiess (Naxess), ranging back to 21.05.2018"""),
        dcc.Graph(id="example-graph", figure=unique_mappers_nominated_fig),
        html.Div(
            [
                "Time period: ",
                dcc.Dropdown(
                    id="period-selector",
                    options=[
                        {"label": "Day", "value": "D"},
                        {"label": "Week", "value": "W"},
                        {"label": "Month", "value": "M"},
                        {"label": "Year", "value": "Y"},
                    ],
                    value=["M"],
                ),
                dcc.Graph(id="ranked_per_period"),
            ]
        ),
    ]
)


@app.callback(
    Output("ranked_per_period", "figure"), [Input("period-selector", "value")]
)
def update_period_figure(period):
    ranked_per_period = methods.maps_per_period(dataframes["mapsets"], period=period[0])

    fig = px.line(ranked_per_period, x="date", y="nr_maps")
    fig.update_layout(transition_duration=500)

    return fig


if __name__ == "__main__":
    app.run_server(debug=True)
