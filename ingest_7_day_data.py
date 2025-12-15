import logging
import ssl
import certifi
import duckdb
import polars as pl
import pandas as pd
from pathlib import Path
from datetime import datetime

# setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# setup duckdb
con = duckdb.connect('migrant_crossings_db.duckdb')
table_name = "raw.migrants_arrived_7_days"

# setup paths
p = Path()
incoming_path = p / 'incoming'
data_path = p / 'data'

# sort ssl issues
ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl._create_default_https_context = lambda: ssl_context

schema_overrides = {
    'Date': pl.String(),
    'Migrants arrived': pl.Int16(),
    'Boats arrived': pl.Int16(),
    'Boats involved in uncontrolled landings': pl.Int16(),
    'Notes': pl.String()
}

schema = [
    'date',
    'migrants_arrived',
    'boats_arrived',
    'boats_arrived_involved_in_uncontrolled_landings',
    'notes'
]

# extract data
gov_web_page = "https://www.gov.uk/government/publications/migrants-detected-crossing-the-english-channel-in-small-boats/migrants-detected-crossing-the-english-channel-in-small-boats-last-7-days"
df = pl.from_pandas(
    data=pd.read_html(gov_web_page)[0],
    schema_overrides=schema_overrides
)

# apply the expected table schema for column names
df.columns = schema

# convert the date
df = df.with_columns(
    pl.col('date').str.strptime(pl.Date,'%d %B %Y').alias('date')
)

# add sdc flags for upsert and merging
current_date = datetime.now().date()
df = df.with_columns(
    pl.lit(f"{current_date}-update").alias('source'),
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
    ON target.date = source.date
    AND target.is_current = true
    WHEN MATCHED AND (
           target.migrants_arrived <> source.migrants_arrived OR
           target.boats_arrived    <> source.boats_arrived    OR
           target.boats_arrived_involved_in_uncontrolled_landings  <> source.boats_arrived_involved_in_uncontrolled_landings OR
           target.notes <> source.notes
        ) THEN UPDATE SET
        end_date    = CURRENT_DATE - INTERVAL '1 day',
        is_current  = false
    WHEN NOT MATCHED BY SOURCE AND target.is_current = true THEN UPDATE SET
        end_date    = CURRENT_DATE - INTERVAL '1 day',
        is_current  = false
    WHEN NOT MATCHED BY TARGET THEN INSERT (
        record_id,
        date,
        migrants_arrived,
        boats_arrived,
        boats_arrived_involved_in_uncontrolled_landings,
        notes,
        source,
        is_current,
        begin_date,
        end_date
    ) VALUES (
        nextval('duck_record_sequence'),
        source.date,
        source.migrants_arrived,
        source.boats_arrived,
        source.boats_arrived_involved_in_uncontrolled_landings,
        source.notes,
        source.source,
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