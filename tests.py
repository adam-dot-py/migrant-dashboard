import duckdb
import altair as alt
import streamlit as st
import polars as pl

# establish a connection to the database
con = duckdb.connect(
    "migrant_crossings_db.duckdb",
    read_only=True
)

# grab some data
df1 = con.execute('SELECT date_ending, migrants_arrived AS "Migrants Arrived", boats_arrived AS "Boats Arrived" FROM latest.migrants_arrived_7_days;').pl()

latest_migrants_arrived = df1['Migrants Arrived'][0]
latest_boats_arrived = df1['Boats Arrived'][0]

print(df1[['date_ending', 'Migrants Arrived']])
con.close()