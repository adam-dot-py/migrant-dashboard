import duckdb
import streamlit as st

# establish a connection to the database
con = duckdb.connect(
    "migrant_crossings_db.duckdb",
    read_only=True
)

# grab some data
df1 = con.execute('SELECT date, migrants_arrived, boats_arrived FROM latest.migrants_arrived_7_days;').pl()
df2 = con.execute('SELECT day_ending, migrants_arrived, boats_arrived FROM latest.migrants_arrived_daily;').pl()

# dashboard things
st.subheader("Transparency data")
st.title("Small boat activity in the English Channel")

# line chart - last 7 days
st.subheader('Small boat arrivals: last 7 days')
st.line_chart(
    data=df1,
    x='date',
    y=['migrants_arrived', 'boats_arrived'],
    x_label='Date',
    y_label='Migrants Arrived'
)

# line chart - last 30 days
st.subheader('Small boat arrivals: last 30 days')
st.line_chart(
    data=df2.limit(30),
    x='day_ending',
    y=['migrants_arrived', 'boats_arrived'],
    x_label='Date',
    y_label='Migrants Arrived'
)

# line chart - last 90 days
st.subheader('Small boat arrivals: last 90 days')
st.line_chart(
    data=df2.limit(90),
    x='day_ending',
    y=['migrants_arrived', 'boats_arrived'],
    x_label='Date',
    y_label='Migrants Arrived'
)

con.close()