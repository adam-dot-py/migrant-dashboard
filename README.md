# Migrant Crossings

:point_right: Check out the [Migrant Crossing dashboard](https://uk-migrant-crossings.streamlit.app) here!

## About

## Managing disinformation

Disinformation is everywhere. With immigration one of the most fiercely debated topics in the UK right now,
social media could be swamped with factually incorrect data, influencing politics and public perception.

This dashboard aims to bring transparency -- at least to figures relating to migrant crossings. There is no disinformation here,
this data comes straight from UK Government statistics and is both fully cited and not altered.

This project holds UK Government statistical data on the number of migrants arriving in the UK 
in small boats and those who were prevented by French authorities from crossing the English 
Channel. The aim of the project is to provide a dashboard for viewing the data interactively, for 
statistical 
analysis and referencing.

All data is taken daily and  weekly from *Transparency data: Small boat activity in the English 
Channel*, 
available [here.](https://www.gov.uk/government/publications/migrants-detected-crossing-the-english-channel-in-small-boats)

## Installation

Install the required dependencies for the project. We recommend using `uv` to set up your 
environment.

### Install `uv`

```commandline
pip install uv
```

Then navigate to the project directory and run:

```commandline
uv sync
```

The required dependencies will then be installed and a new `.venv` will be created for you.

### Querying data

You can query data in the `migrant_crossings_db.duckdb` database using the following (assuming 
you are within the project directory):

```commandline
duckdb migrant_crossings_db.duckdb
```

To view all available tables and views:

```commandline
SHOW ALL TABLES;
```

To query a specific table, reference the schema and table name:

```commandline
SELECT * FROM latest.migrants_arrived_daily;
```