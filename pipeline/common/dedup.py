""" Fetch event deduplication """

from secops_common.bigquery import latest_rows, get_table, insert_rows
from secops_common.functional import merge, compose2, flatten

def get_id(row):
    return row['id']

def new_events(events, fn_id, table):
  get_table(table)
  ids = set(map(fn_id, events))
  query = f"SELECT id FROM $table WHERE ids IN @ids;"
  # ID's are provided externally, we prevent injection
  job_config = bigquery.QueryJobConfig(
    query_parameters=[
        bigquery.ArrayQueryParameter("ids", "STRING", ids),
    ]
  )
  existing = set(map(compose2(get_id, dict), rows))
  new_items = ids - existing
  return list(filter(lambda event: fn_id(event) in new_items , events))


def mark_events(events, fn_id, table):
    stamp = datetime.now(tz=timezone.utc)
    insert_rows(list(map(lambda event: [fn_id(event), stamp], events)), table)
