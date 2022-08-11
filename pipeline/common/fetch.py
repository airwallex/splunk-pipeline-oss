""" Common log audit fetching and persistence """

from datetime import datetime, timedelta, timezone

# Bigquery
import pipeline.common.bigquery
from secops_common.bigquery import latest_rows, get_table, insert_rows

from secops_common.logsetup import logger

# Units
from enum import Enum, auto


class Unit(Enum):
    minutes = auto()
    days = auto()


def into_unit(string):
    return Unit[string]


def last_n_24hours(n, _get_logs, tz=timezone.utc):
    end = datetime.now(tz=tz)
    hours = 24 * n
    delta = timedelta(hours=hours)
    start = end - delta
    return _get_logs(start, end), start, end


def last_n_minutes(n, _get_logs, tz=timezone.utc):
    end = datetime.now(tz=tz)
    delta = timedelta(minutes=n)
    start = end - delta
    return _get_logs(start, end), start, end


def last_from_persisted(time_unit, _get_logs, table, tz=timezone.utc):
    # Making sure table is set
    get_table(table)
    rows = latest_rows(table)
    # Fetching for the very first time (last 5min)
    if rows.total_rows == 0:
        return last_n_minutes(5, _get_logs, tz=tz)
    # Progressing 5 min on top of the persisted data
    else:
        logger.debug(f'Fetching last start/end values from bigquery')
        start, end, status, _ = tuple(list(next(rows.pages))[0])
        logger.debug(f'Date range is {start} - {end}')
        new_start = end.astimezone(tz)
        if time_unit == Unit.days:
            delta = timedelta(hours=24)
        elif time_unit == Unit.minutes:
            delta = timedelta(minutes=5)

        new_end = new_start + delta
        if new_start > datetime.now(tz=tz):
            raise Exception(
                f'date range {new_start}-{new_end} is in the future!')

        return _get_logs(new_start, new_end), new_start, new_end


def mark_last_fetch(start, end, status, table):
    stamp = datetime.now(tz=timezone.utc)
    start_utc = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)
    insert_rows([[start_utc, end_utc, status, stamp]], table)
    if (status == True):
        logger.debug(
            f'Fetching of {table} logs was successful for start {start} - {end} range'
        )
    else:
        logger.debug(
            f'Fetching of {table} logs had failed for start {start} - {end} range'
        )
