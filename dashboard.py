import duckdb

# establish a connection to the database
duckdb_conn = duckdb.connect(
    "migrant_crossings_db.duckdb",
    read_only=True
)

print(duckdb_conn.sql("select * from latest.migrants_arrived_daily limit 2;"))