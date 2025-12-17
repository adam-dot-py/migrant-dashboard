import duckdb
import streamlit as st
import altair as alt
from chart_helper import time_series_chart_maker
from datetime import timedelta
import polars as pl

# establish a connection to the database
con = duckdb.connect(
    "migrant_crossings_db.duckdb",
    read_only=True
)

# grab some data
df1 = con.execute('SELECT date_ending, migrants_arrived, boats_arrived FROM latest.migrants_arrived_7_days;').pl()
df2 = con.execute('SELECT date_ending, migrants_arrived, boats_arrived FROM latest.migrants_arrived_daily;').pl()

# dashboard things

st.set_page_config(
    # Title and icon for the browser's tab bar:
    page_title="Small boat activity in the English Channel",
    # # Make the content take up the width of the page:
    layout="wide"
)

"""
# Small boat activity in the English Channel

A ‘small boat’ is one of a number of vessels used by individuals who cross the English Channel,
with the aim of gaining entry to the UK without a visa or permission to enter – either directly by landing in the UK or having been intercepted at sea by the authorities and brought ashore.
 
The most common small vessels detected making these types of crossings are rigid-hulled inflatable boats (RHIBs), dinghies and kayaks.
"""

latest_date = df1['date_ending'].max()
year_comparison_date = latest_date - timedelta(days=365)
last_week_comparison_date = latest_date - timedelta(days=7)
last_two_weeks_comparison_date = latest_date - timedelta(days=14)
latest_migrants_arrived = df1['migrants_arrived'][0]
latest_boats_arrived = df1['boats_arrived'][0]

# comparisons
comparison_migrants_arrived = df2.filter(pl.col('date_ending') == year_comparison_date )['migrants_arrived'][0]
comparison_migrants_arrived_lw = df2.filter(pl.col('date_ending') == last_week_comparison_date)['migrants_arrived'][0]
comparison_migrants_arrived_lw_2 = df2.filter(pl.col('date_ending') == last_week_comparison_date)['migrants_arrived'][0]

comparison_boats_arrived = df2.filter(pl.col('date_ending') == year_comparison_date )['boats_arrived'][0]
comparison_boats_arrived_lw = df2.filter(pl.col('date_ending') == last_week_comparison_date)['boats_arrived'][0]
comparison_boats_arrived_lw_2 = df2.filter(pl.col('date_ending') == last_week_comparison_date)['boats_arrived'][0]

f"""
## Summary as {latest_date:%d %B %Y}
"""

with st.container(horizontal=True, gap="medium"):

    cols = st.columns(2, gap="medium", width=500)

    with cols[0]:
        st.metric(
            "Latest Migrants Arrived",
            f"{latest_migrants_arrived}",
            delta=f"{latest_migrants_arrived - comparison_migrants_arrived}",
            width="content",
        )

    with cols[1]:
        st.metric(
            "Migrants Arrived Same Day Last Week",
            f"{comparison_migrants_arrived_lw}",
            delta=f"{comparison_migrants_arrived_lw - comparison_migrants_arrived_lw_2}",
            width="content",
        )

    cols = st.columns(2, gap="medium", width=600)

    with cols[0]:
        st.metric(
            "Latest Boats Arrived",
            f"{latest_boats_arrived}",
            delta=f"{latest_boats_arrived - comparison_boats_arrived}",
            width="content",
        )

    with cols[1]:
        st.metric(
            "Boats Arrived Same Day Last Week",
            f"{comparison_boats_arrived_lw}",
            delta=f"{comparison_boats_arrived_lw - comparison_boats_arrived_lw_2}",
            width="content",
        )

"""
### Migrants arrived on small boats: last 7 days
"""

cols = st.columns(1)
with cols[0].container(border=True, height="stretch"):
    st.altair_chart(
        alt.Chart(df1)
        .mark_bar()
        .encode(
            alt.X(
                "date_ending:N",
                timeUnit="yearmonthdate",
                title="Date",
                axis=alt.Axis(
                    format="%e %b",
                    tickBand='center'
                )
            ),
            alt.Y(
                "migrants_arrived:Q",
                aggregate="sum",
                title="Migrants Arrived"
            )
        )
    )

seven_days_source_text = """
Source: 
<a href="https://www.gov.uk/government/publications/migrants-detected-crossing-the-english-channel-in-small-boats/migrants-detected-crossing-the-english-channel-in-small-boats-last-7-days" 
   target="_blank" 
   rel="noopener noreferrer">
  Migrants detected crossing the English Channel in small boats (last 7 days)
</a>
"""
st.html(seven_days_source_text)

"""
## Time-series data
"""

st.info("Statistical data for the below tables is updated every Friday")

daily_source_text = """
Source: 
<a href="https://www.gov.uk/government/publications/migrants-detected-crossing-the-english-channel-in-small-boats" 
   target="_blank" 
   rel="noopener noreferrer">
  Small boat activity in the English Channel
</a>
"""

# setup structure
cols = st.columns(2)

with cols[0].container(border=True, height="stretch"):
    "### Migrants arrived on small boats: last 30 days"

    seven_days_chart = time_series_chart_maker(data=df1, time_series=7, tickCount=7)
    st.altair_chart(seven_days_chart, use_container_width=True)

with cols[1].container(border=True, height="stretch"):
    "### Migrants arrived on small boats: last 90 days"

    thirty_days_chart = time_series_chart_maker(data=df2, time_series=30, tickCount=15)
    st.altair_chart(thirty_days_chart, use_container_width=True)

st.html(daily_source_text)

"""
## Historical data
"""

cols = st.columns(1)
with cols[0].container(border=True, height="stretch"):
    st.altair_chart(
            alt.Chart(df2[['date_ending', 'migrants_arrived']])
            .mark_bar()
            .encode(
                alt.X("date_ending:N", timeUnit="month").title("Date"),
                alt.Y("migrants_arrived:Q").aggregate("sum").title("Migrants Arrived"),
                alt.Color("date_ending:N", timeUnit="year").title("Year"),
            )
            .configure_legend(orient="bottom")
        )

st.html(daily_source_text)

con.close()