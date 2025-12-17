import streamlit as st
import altair as alt

def time_series_chart_maker(data, time_series: None, tickCount):
    chart = (
        alt.Chart(data.limit(time_series))
        .transform_fold(
            ["migrants_arrived", "boats_arrived"],
            as_=["metric", "value"]
        )
        .mark_line(point=True)
        .encode(
            x=alt.X(
                "date_ending:T",
                title="Date",
                axis=alt.Axis(
                    format="%d %b",      # e.g. 03 Jan
                    labelAngle=-90,
                    tickCount=tickCount
                )
            ),
            y=alt.Y(
                "value:Q",
                title="Migrants / Boats Arrived"
            ),
            color=alt.Color(
                "metric:N",
                title="Metric"
            ),
            tooltip=[
                alt.Tooltip("date_ending:T", title="Date", format="%d %b %Y"),
                alt.Tooltip("metric:N", title="Metric"),
                alt.Tooltip("value:Q", title="Value")
            ]
        ).configure_legend(orient="bottom")
    )

    return chart