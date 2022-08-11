""" Common log audit fetching and persistence """

from datetime import datetime, timedelta, timezone

# Bigquery
import pipeline.common.bigquery
from secops_common.bigquery import latest_rows, get_table, insert_rows

from secops_common.logsetup import logger

# Units
from enum import Enum, auto


def last_n_minutes(n, _get_logs, tz=timezone.utc):
    end = datetime.now(tz=tz)
    delta = timedelta(minutes=n)
    start = end - delta
    return _get_logs(start, end), start, end


def last_from_persisted_windowed(_get_logs, table):
    # Making sure table is set
    get_table(table)
    rows = latest_rows(table)
    # Fetching for the very first time (no prior state)
    if rows.total_rows == 0:
        return last_n_minutes(5, _get_logs)
    else:
        logger.debug(f'Fetching last start/end values from bigquery')
        start, end, status, _ = tuple(list(next(rows.pages))[0])
        logger.debug(f'Date range is {start} - {end}')
        return _get_logs(start, end), start, end


def mark_last_fetch_windowed(start, event_count, last_event_date, table):
    stamp = datetime.now(tz=timezone.utc)
    # No events found (yet) moving end to current time
    if (event_count == 0):
        insert_rows([[start, stamp, False, stamp]], table)
    # Events found, window is moving ahead
    else:
        # Making the next fetch non inclusive adding one mili second
        plus_1 = last_event_date + 1
        insert_rows([[plus_1, stamp, True, stamp]], table)
