""" Fetch event deduplication """

from secops_common.bigquery import get_table, insert_rows, run_query
from secops_common.functional import merge, compose2, flatten

from google.cloud import bigquery

from pipeline.common.config import CONFIG

from datetime import datetime, timezone

def get_id(row):
    return row['id']

project = CONFIG['project']
dataset = CONFIG['dataset']

def new_events(events, fn_id, table):
  get_table(table)
  ids = set(map(fn_id, events))
  query = f"SELECT id FROM `{project}.{dataset}.{table}` WHERE id IN UNNEST(@ids);"
  # As ID's are provided externally, we prevent injection by using a prep statement
  job_config = bigquery.QueryJobConfig(
    query_parameters=[
        bigquery.ArrayQueryParameter("ids", "STRING", ids),
    ]
  )
  rows = run_query(query, config=job_config)
  existing = set(map(compose2(get_id, dict), rows))
  new_items = ids - existing
  return list(filter(lambda event: fn_id(event) in new_items , events))


def mark_events(events, fn_id, table):
    if events:
      get_table(table)
      stamp = datetime.now(tz=timezone.utc)
      insert_rows(list(map(lambda event: [fn_id(event), stamp], events)), table)

