# DLT (Data Load Tool) Cheat Sheet

> **dlt** is an open-source Python library that lets you build, run, and maintain data pipelines
> without writing boilerplate. It handles schema inference, data normalisation, incremental loading,
> and destination management so you can focus on your data instead of your infrastructure.

---

## Table of Contents

1. [Core Concepts](#1-core-concepts)
2. [Installation & Quick Start](#2-installation--quick-start)
3. [Sources & Resources](#3-sources--resources)
4. [Custom Connectors](#4-custom-connectors)
5. [REST API Sources](#5-rest-api-sources)
6. [Write Dispositions](#6-write-dispositions)
7. [Incremental Loading](#7-incremental-loading)
8. [Schema Management](#8-schema-management)
9. [Secrets & Configuration](#9-secrets--configuration)
10. [Destinations](#10-destinations)
11. [Using DLT in Databricks](#11-using-dlt-in-databricks)
12. [Running & Deploying Pipelines](#12-running--deploying-pipelines)
13. [Transformations & dbt Integration](#13-transformations--dbt-integration)
14. [Monitoring & Alerting](#14-monitoring--alerting)
15. [Common Patterns & Tips](#15-common-patterns--tips)

---

## 1. Core Concepts

| Concept | Description |
|---|---|
| **Pipeline** | A named end-to-end flow: source → normalise → destination |
| **Source** | A decorated Python function (or class) that yields data |
| **Resource** | A single stream of data within a source (e.g. one API endpoint) |
| **Destination** | Where data lands (DuckDB, BigQuery, Snowflake, Databricks, …) |
| **Schema** | Auto-inferred table definitions; exportable and version-controlled |
| **Write Disposition** | How data is written: `append`, `replace`, or `merge` |
| **Staging** | Optional intermediate storage (e.g. S3/GCS) before loading |

### Pipeline lifecycle

```
Source (yield data)
  → Normaliser (infer types, flatten nested JSON)
    → Load (write to destination using the write disposition)
```

---

## 2. Installation & Quick Start

```bash
pip install dlt                         # core
pip install "dlt[duckdb]"               # + DuckDB destination
pip install "dlt[bigquery]"             # + BigQuery destination
pip install "dlt[databricks]"           # + Databricks destination
pip install "dlt[rest_api]"             # + REST API helpers
```

### Minimal pipeline

```python
import dlt

@dlt.resource
def my_data():
    yield [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

pipeline = dlt.pipeline(
    pipeline_name="my_pipeline",
    destination="duckdb",
    dataset_name="my_schema",
)

load_info = pipeline.run(my_data())
print(load_info)
```

---

## 3. Sources & Resources

### `@dlt.source`

Groups multiple related resources under one logical source.

```python
@dlt.source
def my_api_source(api_key=dlt.secrets.value):
    return [users_resource(api_key), orders_resource(api_key)]
```

### `@dlt.resource`

Yields records one-by-one or in batches.

```python
@dlt.resource(
    name="users",                   # table name (defaults to function name)
    write_disposition="append",     # append | replace | merge
    primary_key="id",               # used for merge deduplication
    columns={"email": {"data_type": "text", "nullable": False}},
)
def users_resource(api_key):
    for page in fetch_pages(api_key):
        yield page                  # yield a list or individual dicts
```

### Transformer resources

Process the output of another resource:

```python
@dlt.transformer(data_from=users_resource)
def user_details(user):
    yield fetch_user_detail(user["id"])
```

### Selecting resources at runtime

```python
source = my_api_source()
source.resources["users"].selected = True
source.resources["orders"].selected = False
pipeline.run(source)
```

---

## 4. Custom Connectors

Build a fully custom source when there is no existing verified source for your system.

### Step-by-step pattern

```python
import dlt
import requests

BASE_URL = "https://api.example.com/v1"

def _get_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

@dlt.resource(write_disposition="replace")
def products(api_key: str = dlt.secrets.value):
    """Yields all products from the Example API."""
    url = f"{BASE_URL}/products"
    while url:
        resp = requests.get(url, headers=_get_headers(api_key))
        resp.raise_for_status()
        data = resp.json()
        yield data["items"]            # yield a batch
        url = data.get("next_page")    # follow pagination

@dlt.resource(write_disposition="append", primary_key="id")
def orders(
    api_key: str = dlt.secrets.value,
    updated_at: dlt.sources.incremental[str] = dlt.sources.incremental(
        "updated_at", initial_value="2020-01-01T00:00:00Z"
    ),
):
    """Incrementally loads orders updated since last run."""
    url = f"{BASE_URL}/orders"
    params = {"updated_after": updated_at.last_value}
    resp = requests.get(url, headers=_get_headers(api_key), params=params)
    resp.raise_for_status()
    yield resp.json()["orders"]

@dlt.source
def example_source(api_key: str = dlt.secrets.value):
    return [products(api_key), orders(api_key)]

# Run it
if __name__ == "__main__":
    pipeline = dlt.pipeline("example", destination="duckdb", dataset_name="raw")
    pipeline.run(example_source())
```

### Key decorator parameters

| Parameter | Type | Purpose |
|---|---|---|
| `name` | `str` | Override the table/resource name |
| `write_disposition` | `str` | `append`, `replace`, `merge` |
| `primary_key` | `str \| list[str]` | Column(s) used as PK for merge/dedup |
| `merge_key` | `str \| list[str]` | Overrides primary_key for merge matching |
| `columns` | `dict` | Column hints (type, nullable, precision, …) |
| `parallelized` | `bool` | Run resource in a thread pool |
| `max_table_nesting` | `int` | Limit depth of nested JSON unpacking |
| `selected` | `bool` | Include/exclude from pipeline run |

---

## 5. REST API Sources

dlt ships a generic `rest_api` helper that eliminates repetitive boilerplate for REST pagination, authentication, and incremental cursors.

### Config-driven REST source

```python
from dlt.sources.rest_api import rest_api_source

source = rest_api_source({
    "client": {
        "base_url": "https://api.github.com/",
        "auth": {
            "type": "bearer",
            "token": dlt.secrets["github_token"],
        },
        "paginator": {
            "type": "link_header",          # follows GitHub's Link: <...>; rel="next"
        },
    },
    "resource_defaults": {
        "write_disposition": "merge",
        "primary_key": "id",
    },
    "resources": [
        {
            "name": "repos",
            "endpoint": {
                "path": "orgs/{org}/repos",
                "params": {"org": "dlt-hub", "per_page": 100},
            },
        },
        {
            "name": "issues",
            "endpoint": {
                "path": "repos/{org}/{repo}/issues",
                "params": {
                    "org": "dlt-hub",
                    "repo": {
                        "type": "resolve",   # resolve from parent resource
                        "resource": "repos",
                        "field": "name",
                    },
                    "state": "all",
                    "per_page": 100,
                },
                "incremental": {
                    "cursor_path": "updated_at",
                    "initial_value": "2020-01-01T00:00:00Z",
                },
            },
        },
    ],
})

pipeline = dlt.pipeline("github", destination="duckdb", dataset_name="github_data")
pipeline.run(source)
```

### Supported paginators

| Type | When to use |
|---|---|
| `link_header` | GitHub-style `Link` response header |
| `page_number` | `?page=1`, `?page=2`, … |
| `offset` | `?offset=0&limit=100`, `?offset=100&limit=100`, … |
| `cursor` | Cursor token returned in response body |
| `json_link` | Next-page URL embedded in response JSON |
| `single_page` | No pagination (returns one response) |

### Supported auth types

| Type | Config keys |
|---|---|
| `bearer` | `token` |
| `api_key` | `name`, `api_key`, `location` (`header`/`query`) |
| `http_basic` | `username`, `password` |
| `oauth2_client_credentials` | `client_id`, `client_secret`, `token_url` |

### Resource-level endpoint options

```python
{
    "name": "events",
    "endpoint": {
        "path": "events",
        "method": "GET",              # GET (default) | POST
        "params": {"limit": 50},      # query string params
        "json": {"filter": "active"}, # POST body (when method=POST)
        "incremental": {
            "cursor_path": "created_at",
            "initial_value": "2023-01-01",
            "end_value": "2024-01-01",    # optional upper bound
            "convert": "pendulum.parse",  # transform cursor value
        },
        "response_actions": [         # map HTTP status codes
            {"status_code": 429, "action": "retry"},
            {"status_code": 404, "action": "ignore"},
        ],
    },
    "write_disposition": "append",
    "primary_key": "event_id",
}
```

---

## 6. Write Dispositions

Write dispositions control **how** dlt writes new data to the destination table.

### `append`

> Always add rows. Never delete or update existing rows.

```python
@dlt.resource(write_disposition="append")
def events():
    yield [{"event_id": 1, "ts": "2024-01-01"}]
```

- **Use when:** event/log tables, immutable records, audit trails.
- **Effect:** Every run adds rows. Duplicate rows accumulate if the source resends data.

---

### `replace`

> Drop and recreate the table on every run.

```python
@dlt.resource(write_disposition="replace")
def lookup_countries():
    yield [{"code": "GB", "name": "United Kingdom"}]
```

- **Use when:** small reference/lookup tables that are fully refreshed.
- **Effect:** Old data is gone after each run. No merge keys needed.

> **Staging replace (recommended for large tables):**
> ```python
> @dlt.resource(
>     write_disposition={"disposition": "replace", "strategy": "staging-optimized"}
> )
> def large_table(): ...
> ```
> Loads into a staging table first, then swaps atomically.

---

### `merge`

> Upsert rows: insert new, update existing (matched on `primary_key`), optionally delete removed rows.

```python
@dlt.resource(
    write_disposition="merge",
    primary_key="user_id",
)
def users():
    yield [{"user_id": 1, "name": "Alice", "updated_at": "2024-06-01"}]
```

- **Use when:** slowly changing dimension (SCD1), entities that change over time.
- **Requires:** `primary_key` to identify matching rows.

#### Merge with hard deletes

```python
@dlt.resource(
    write_disposition={
        "disposition": "merge",
        "strategy": "delete-insert",   # default strategy
        "hard_delete": "is_deleted",   # bool column → deletes matching rows
    },
    primary_key="id",
)
def contacts():
    yield [{"id": 1, "name": "Bob", "is_deleted": False}]
```

#### SCD2 (keep full history)

```python
@dlt.resource(
    write_disposition={
        "disposition": "merge",
        "strategy": "scd2",
    },
    primary_key="id",
    merge_key="id",
)
def customers():
    yield [{"id": 1, "status": "gold", "updated_at": "2024-07-01"}]
```

dlt automatically adds `_dlt_valid_from`, `_dlt_valid_to`, and `_dlt_active` columns.

### Write disposition comparison

| Feature | `append` | `replace` | `merge` |
|---|---|---|---|
| Adds new rows | ✅ | ✅ (full refresh) | ✅ |
| Updates existing rows | ❌ | ✅ (via drop) | ✅ |
| Deletes removed rows | ❌ | ✅ (via drop) | ✅ (hard delete) |
| Requires primary key | ❌ | ❌ | ✅ |
| Supports SCD2 | ❌ | ❌ | ✅ |
| Best for | Events, logs | Reference data | Entities, SCD |

---

## 7. Incremental Loading

Avoid re-loading data you already have.

### Cursor-based incremental

```python
@dlt.resource(write_disposition="append")
def orders(
    updated_at: dlt.sources.incremental[str] = dlt.sources.incremental(
        cursor_path="updated_at",           # JSON path to the cursor field
        initial_value="2020-01-01",         # used on first run only
        end_value=None,                     # optional upper bound
        lag=3600,                           # overlap window (seconds) for late arrivals
    )
):
    params = {"updated_after": updated_at.last_value}
    yield requests.get(URL, params=params).json()["orders"]
```

### Primary-key deduplication

When `write_disposition="merge"` is combined with `primary_key`, dlt automatically deduplicates within a load batch and upserts against the destination.

### Saving and inspecting state

```python
# dlt stores the last cursor value in pipeline state automatically.
# Inspect it:
print(pipeline.state)

# Reset state to force a full reload:
pipeline.drop_state()          # clears state only (keeps tables)
# or
pipeline.drop()                # clears state AND drops all tables
```

---

## 8. Schema Management

### Auto-inference

dlt infers column types from Python types on the first run. Subsequent runs evolve the schema non-destructively (new columns are added; existing columns are never dropped).

### Explicit column hints

```python
@dlt.resource(
    columns={
        "id":         {"data_type": "bigint",    "nullable": False},
        "email":      {"data_type": "text",       "nullable": True},
        "created_at": {"data_type": "timestamp",  "nullable": False},
        "amount":     {"data_type": "decimal",    "precision": 18, "scale": 4},
    }
)
def payments(): ...
```

### Exporting & importing schemas

```bash
# Export schema to YAML
dlt schema export my_pipeline --destination duckdb

# Schemas are also stored in .dlt/schemas/
```

### Data type map

| Python type | dlt inferred type |
|---|---|
| `int` | `bigint` |
| `float` | `double` |
| `str` | `text` |
| `bool` | `bool` |
| `datetime` | `timestamp` |
| `date` | `date` |
| `dict` | flattened columns or `json` |
| `list[dict]` | child table (nested) |

---

## 9. Secrets & Configuration

dlt resolves secrets and config through a layered lookup:

```
environment variables  →  .dlt/secrets.toml  →  .dlt/config.toml  →  defaults
```

### `.dlt/secrets.toml`

```toml
[sources.my_api]
api_key = "super-secret-key"

[destination.bigquery]
credentials = {project_id = "my-project", private_key = "..."}
```

### `.dlt/config.toml`

```toml
[sources.my_api]
base_url = "https://api.example.com/v1"
page_size = 100
```

### Environment variables

```bash
# Format: SECTION__SUBSECTION__KEY  (double underscore separator)
export SOURCES__MY_API__API_KEY="super-secret-key"
export DESTINATION__BIGQUERY__CREDENTIALS__PROJECT_ID="my-project"
```

### Injecting secrets into functions

```python
@dlt.resource
def my_resource(
    api_key: str = dlt.secrets.value,           # required; raises if missing
    page_size: int = dlt.config.value,          # from config (non-secret)
    timeout: int = 30,                          # plain default
):
    ...
```

### Using external secret managers

```python
# AWS Secrets Manager, GCP Secret Manager, Azure Key Vault, Airflow Variables
# are all supported via provider plugins — configure in .dlt/config.toml:
# [providers]
# type = "aws_secrets_manager"
# region = "eu-west-1"
```

---

## 10. Destinations

### Built-in destinations (selection)

| Destination | Install extra | Notes |
|---|---|---|
| `duckdb` | `dlt[duckdb]` | Local dev / embedded analytics |
| `filesystem` | `dlt[filesystem]` | Parquet/JSONL to S3, GCS, Azure |
| `bigquery` | `dlt[bigquery]` | Google BigQuery |
| `snowflake` | `dlt[snowflake]` | Snowflake |
| `redshift` | `dlt[redshift]` | Amazon Redshift |
| `databricks` | `dlt[databricks]` | Databricks SQL Warehouse / Unity Catalog |
| `postgres` | `dlt[postgres]` | PostgreSQL / Aurora |
| `synapse` | `dlt[synapse]` | Azure Synapse Analytics |
| `mssql` | `dlt[mssql]` | Microsoft SQL Server |
| `motherduck` | `dlt[motherduck]` | MotherDuck (cloud DuckDB) |
| `weaviate` | `dlt[weaviate]` | Vector DB for AI/ML workloads |
| `lancedb` | `dlt[lancedb]` | Local/cloud vector store |

### Configuring a destination inline

```python
pipeline = dlt.pipeline(
    pipeline_name="my_pipeline",
    destination=dlt.destinations.bigquery(
        credentials={"project_id": "my-project"},
        location="EU",
    ),
    dataset_name="raw_data",
    staging=dlt.destinations.filesystem("s3://my-bucket/staging"),
)
```

---

## 11. Using DLT in Databricks

### Installation on a Databricks cluster

```bash
# In a Databricks notebook cell:
%pip install "dlt[databricks]"
```

Or add `dlt[databricks]` to your cluster's library configuration (PyPI).

### Connecting to a Databricks SQL Warehouse

```python
import dlt

pipeline = dlt.pipeline(
    pipeline_name="databricks_pipeline",
    destination="databricks",
    dataset_name="bronze",                 # maps to a Unity Catalog schema
)
```

#### Credentials in `.dlt/secrets.toml`

```toml
[destination.databricks.credentials]
server_hostname  = "<workspace>.azuredatabricks.net"
http_path        = "/sql/1.0/warehouses/<warehouse-id>"
access_token     = "<personal-access-token>"
catalog          = "main"          # Unity Catalog (optional, defaults to hive_metastore)
```

#### Or via environment variables

```bash
export DESTINATION__DATABRICKS__CREDENTIALS__SERVER_HOSTNAME="<workspace>.azuredatabricks.net"
export DESTINATION__DATABRICKS__CREDENTIALS__HTTP_PATH="/sql/1.0/warehouses/<id>"
export DESTINATION__DATABRICKS__CREDENTIALS__ACCESS_TOKEN="<token>"
export DESTINATION__DATABRICKS__CREDENTIALS__CATALOG="main"
```

### Running a pipeline in a Databricks notebook

```python
import dlt
from dlt.sources.rest_api import rest_api_source

# 1. Define your source
source = rest_api_source({
    "client": {"base_url": "https://api.example.com"},
    "resources": [{"name": "events", "endpoint": {"path": "events"}}],
})

# 2. Create pipeline targeting Databricks
pipeline = dlt.pipeline(
    pipeline_name="events_pipeline",
    destination="databricks",
    dataset_name="raw",
)

# 3. Run
load_info = pipeline.run(source)
print(load_info)
```

### Using staging (recommended for large loads)

Databricks works best when data is staged in cloud object storage first.

```toml
# .dlt/config.toml
[destination.filesystem]
bucket_url = "abfss://container@account.dfs.core.windows.net/staging"

[destination.filesystem.credentials]
azure_storage_account_name = "myaccount"
azure_storage_account_key  = "..."
```

```python
pipeline = dlt.pipeline(
    destination="databricks",
    staging=dlt.destinations.filesystem(
        "abfss://container@account.dfs.core.windows.net/staging"
    ),
    dataset_name="bronze",
)
```

### Unity Catalog integration

```toml
[destination.databricks.credentials]
catalog = "my_catalog"        # target Unity Catalog
```

- Tables land in `<catalog>.<dataset_name>.<resource_name>`.
- dlt applies the configured write disposition using `MERGE INTO` for merge, `INSERT INTO` for append, and `CREATE OR REPLACE TABLE` for replace.

### Running as a Databricks Job

1. Upload your pipeline script to DBFS or a Databricks Repo.
2. Create a **Job** with a Python task pointing to your script.
3. Set cluster libraries to include `dlt[databricks]`.
4. Store secrets in **Databricks Secrets** and expose them as environment variables in the Job config:
   ```
   DESTINATION__DATABRICKS__CREDENTIALS__ACCESS_TOKEN = {{secrets/scope/token}}
   ```

### Delta Live Tables vs. dlt

> **Note:** Databricks also has a product called **Delta Live Tables (DLT)**. This is *different* from the `dlt` Python library.
>
> | | dlt (Python library) | Delta Live Tables (Databricks) |
> |---|---|---|
> | Open source | ✅ | ❌ (Databricks-only) |
> | Multi-destination | ✅ | ❌ |
> | Declarative SQL | ❌ | ✅ |
> | Python sources | ✅ | ✅ |
> | REST API helpers | ✅ | ❌ |
> | Runs anywhere | ✅ | ❌ (Databricks only) |
>
> `dlt` (the Python library) *can write data into Databricks* alongside or instead of Delta Live Tables.

---

## 12. Running & Deploying Pipelines

### Running locally

```python
load_info = pipeline.run(source)
print(load_info)              # summary of loaded rows, tables, load IDs
print(pipeline.last_trace)    # detailed timing & diagnostics
```

### CLI commands

```bash
dlt pipeline list                     # list all local pipelines
dlt pipeline <name> info              # show pipeline state
dlt pipeline <name> show              # open Streamlit explorer (requires streamlit)
dlt pipeline <name> trace             # show last run trace
dlt pipeline <name> drop              # drop state + tables
dlt pipeline <name> sync              # sync schema from destination
```

### Deploying to Airflow

```bash
dlt deploy my_pipeline.py airflow-composer \
  --schedule "0 6 * * *" \
  --location europe-west2
```

Generates a ready-to-use Airflow DAG file.

### Deploying to GitHub Actions

```bash
dlt deploy my_pipeline.py github-action --schedule "0 6 * * *"
```

### Deploying to other orchestrators

dlt integrates with **Prefect**, **Dagster**, **Kestra**, **Modal**, **Cloud Functions**, and more via community providers.

---

## 13. Transformations & dbt Integration

### In-pipeline transformations (add_map / add_filter)

```python
def clean_email(row):
    row["email"] = row["email"].strip().lower()
    return row

resource = users_resource()
resource.add_map(clean_email)
resource.add_filter(lambda row: row.get("active", False))
```

### Running dbt after load

```python
from dlt.helpers.dbt import create_runner

pipeline = dlt.pipeline(...)
pipeline.run(source)

dbt = create_runner(
    pipeline,
    venv=None,                       # or path to venv with dbt installed
    package_location="./dbt_project",
    destination_type="bigquery",
)
models = dbt.run_all()
```

### Using `sqlmesh` or raw SQL

```python
with pipeline.sql_client() as client:
    client.execute_sql("""
        CREATE OR REPLACE TABLE gold.user_summary AS
        SELECT user_id, COUNT(*) AS event_count
        FROM raw.events
        GROUP BY 1
    """)
```

---

## 14. Monitoring & Alerting

### Load info object

```python
load_info = pipeline.run(source)

for package in load_info.load_packages:
    print(package.load_id, package.state)
    for table, jobs in package.jobs.items():
        for job in jobs:
            print(f"  {table}: {job.state} ({job.file_path})")
```

### Raising on load errors

```python
load_info.raise_on_failed_jobs()   # raises DataLoadIncompleteException
```

### Sending Slack alerts

```python
from dlt.common.runtime.slack import send_slack_message

try:
    load_info = pipeline.run(source)
    load_info.raise_on_failed_jobs()
    send_slack_message(
        incoming_hook=dlt.secrets["slack_webhook"],
        message=f"✅ Pipeline succeeded: {load_info}",
    )
except Exception as e:
    send_slack_message(
        incoming_hook=dlt.secrets["slack_webhook"],
        message=f"❌ Pipeline failed: {e}",
    )
```

---

## 15. Common Patterns & Tips

### Parallel resource loading

```python
@dlt.resource(parallelized=True)
def parallel_resource():
    yield from fetch_all_pages()
```

### Flattening nested JSON

```python
# dlt flattens nested dicts to columns automatically:
# {"user": {"id": 1, "name": "Alice"}}
# → columns: user__id, user__name

# Nested lists become child tables:
# {"id": 1, "tags": ["a", "b"]}
# → parent table: id=1 | child table: id=..., tags__value="a", tags__value="b"

# Limit nesting depth:
@dlt.resource(max_table_nesting=0)  # store nested JSON as raw JSON column
def flat_resource(): ...
```

### Adding custom metadata columns

```python
import pendulum

@dlt.resource
def enriched_events():
    for event in fetch_events():
        event["_loaded_at"] = pendulum.now().isoformat()
        yield event
```

### Handling API rate limits with retry

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=60))
def fetch_with_retry(url, headers):
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()
```

### Dry-run / extract only

```python
# Extract data locally without loading to destination
pipeline.extract(source)
# Data files are written to pipeline.working_dir
```

### Inspecting extracted data before load

```python
pipeline.extract(source)
pipeline.normalize()

with pipeline.sql_client() as client:
    df = client.execute_sql("SELECT * FROM events LIMIT 10")
    print(df)
```

### Environment-based destination switching

```python
import os

dest = os.getenv("DLT_DESTINATION", "duckdb")

pipeline = dlt.pipeline(
    pipeline_name="my_pipeline",
    destination=dest,
    dataset_name="raw",
)
```

---

## Quick-Reference Card

```
┌─────────────────────────────────────────────────────────────────┐
│  dlt QUICK REFERENCE                                            │
├─────────────────┬───────────────────────────────────────────────┤
│ Create pipeline │ dlt.pipeline(name, destination, dataset_name) │
│ Define source   │ @dlt.source                                   │
│ Define resource │ @dlt.resource(write_disposition=..., pk=...)  │
│ Run pipeline    │ pipeline.run(source_or_resource)              │
│ Incremental     │ dlt.sources.incremental("cursor_col", "val")  │
├─────────────────┼───────────────────────────────────────────────┤
│ append          │ Add rows, never modify existing               │
│ replace         │ Drop + reload full table every run            │
│ merge           │ Upsert on primary_key; optional SCD2          │
├─────────────────┼───────────────────────────────────────────────┤
│ Secrets file    │ .dlt/secrets.toml                             │
│ Config file     │ .dlt/config.toml                              │
│ Env var pattern │ SECTION__SUBSECTION__KEY                      │
├─────────────────┼───────────────────────────────────────────────┤
│ Databricks dest │ dlt[databricks] + credentials in secrets.toml │
│ REST API helper │ dlt[rest_api] + rest_api_source({...})        │
│ dbt integration │ dlt.helpers.dbt.create_runner(pipeline, ...)  │
└─────────────────┴───────────────────────────────────────────────┘
```

---

*Generated for dlt ≥ 0.5.x — refer to the [official dlt docs](https://dlthub.com/docs) for the latest API.*
