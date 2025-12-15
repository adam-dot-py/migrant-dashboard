import logging
import duckdb
import polars as pl
from pathlib import Path
from datetime import datetime
from extract_data import fetch_migrant_data

# setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# setup paths
p = Path()
data_path = p / 'data'

# fetch latest data
fetch_migrant_data()

# setup duckdb
con = duckdb.connect('migrant_crossings_db.duckdb')
table_name = "raw.migrants_arrived_weekly"

schema_overrides = {
    'Week ending': pl.Date(),
    'Migrants arrived': pl.Int16(),
    'Boats arrived': pl.Int16(),
    'Boats arrived - involved in uncontrolled landings': pl.Int16(),
    'Migrants prevented': pl.Int16(),
    'Events prevented': pl.Int16(),
    'Notes': pl.String()
}

schema = [
    'week_ending',
    'migrants_arrived',
    'boats_arrived',
    'boats_arrived_involved_in_uncontrolled_landings',
    'migrants_prevented',
    'events_prevented',
    'notes'
]

all_data = []
for f in data_path.glob('*.ods'):
    _df = pl.read_ods(
        source=f,
        schema_overrides=schema_overrides,
        sheet_name='SB_02'
    )
    all_data.append(_df)

# create the polars dataframe
df = pl.concat(all_data)

# sort by date descending (latest first)
df = df.sort(by=pl.col('week_ending'), descending=True)

# add sdc flags for upsert and merging
current_date = datetime.now().date()
df = df.with_columns(
    pl.lit(True).alias('is_current'),
    pl.lit(current_date).alias('begin_date').cast(pl.Date()),
    pl.lit(None).alias('end_date').cast(pl.Date())
)

# register the df for ingestion into the database
con.register('polarsDF', df)

# upsert and merge
try:
    logging.info("Attempting merge...")
    con.sql(f"""
    MERGE into {table_name} AS target
    USING polarsDF AS source
    ON target.week_ending = source.week_ending
    AND target.is_current = true
    WHEN MATCHED AND (
           target.migrants_arrived <> source.migrants_arrived OR
           target.boats_arrived    <> source.boats_arrived    OR
           target.boats_arrived_involved_in_uncontrolled_landings  <> source.boats_arrived_involved_in_uncontrolled_landings OR
           target.migrants_prevented <> source.migrants_prevented OR
           target.events_prevented <> source.events_prevented OR
           target.notes <> source.notes
        ) THEN UPDATE SET
        end_date    = CURRENT_DATE - INTERVAL '1 day',
        is_current  = false
    WHEN NOT MATCHED BY SOURCE AND target.is_current = true THEN UPDATE SET
        end_date    = CURRENT_DATE - INTERVAL '1 day',
        is_current  = false
    WHEN NOT MATCHED BY TARGET THEN INSERT (
        record_id,
        week_ending,
        migrants_arrived,
        boats_arrived,
        boats_arrived_involved_in_uncontrolled_landings,
        migrants_prevented,
        events_prevented,
        notes,
        is_current,
        begin_date,
        end_date
    ) VALUES (
        nextval('duck_record_sequence'),
        source.week_ending,
        source.migrants_arrived,
        source.boats_arrived,
        source.boats_arrived_involved_in_uncontrolled_landings,
        source.migrants_prevented,
        source.events_prevented,
        source.notes,
        source.is_current,
        source.begin_date,
        source.end_date
    )
    """)
    logging.info(f"Updated -> {table_name}")
except Exception as e:
    logging.critical(f"Something went wrong -> {e}")

con.close()
logging.info("Connection to duckdb closed")