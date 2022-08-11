#!/usr/bin/env python3
"""Google workspace logs"""

from pipeline.common.time import microseconds, unix_time_millis

from pipeline.common.splunk import publish, retryable
from pipeline.common.functional import partition
from pipeline.common.fetch import last_n_24hours, last_n_minutes, Unit, into_unit
from pipeline.common.window import last_from_persisted_windowed, mark_last_fetch_windowed

from secops_common.logsetup import logger, enable_logfile

from secops_common.secrets import read_config

# Bigquery
import pipeline.common.bigquery
from secops_common.bigquery import run_query

# UI
import pprint
import click

import datetime

from pipeline.common.config import CONFIG

pp = pprint.PrettyPrinter(indent=4)

project_id = CONFIG['project_id']


@click.group()
def cli():
    pass


project = CONFIG['project']


def query(start, end):
    # See https://support.google.com/a/answer/7234657?product_name=UnuFlow&hl=en&visit_id=637885264241168345-3671120257&rd=1&src=supportwidget0&hl=en
    # Note the timestamp_usec has to be converted using a BQ function! (it won't work otherwise)
    return f"""SELECT TIMESTAMP_MICROS(event_info.timestamp_usec) as timestamp, event_info, message_info FROM `{project}.gmail_logs_dataset.daily_*` where
                  (_TABLE_SUFFIX BETWEEN '{start.strftime('%Y%m%d')}' AND '{end.strftime('%Y%m%d')}')
                     AND
                  event_info.timestamp_usec > {microseconds(start)}
                     AND
                  event_info.timestamp_usec <= {microseconds(end)}"""


def _get_logs(start, end):
    rows = run_query(query(start, end))
    results = list(map(dict, rows))
    logger.debug(f'Total of {len(results)} logs fetched in _get_logs Gmail')
    return results


def with_time(log):
    log['timestamp'] = unix_time_millis(log['timestamp'])
    return log


BATCH_SIZE = 5000


def _publish_gmail_logs(num, unit):
    time_unit = into_unit(unit)
    if (int(num) > 0):
        logger.info(f'Publishing Gmail logs for {num} {unit}')
        if (time_unit == Unit.days):
            logs, _, _ = last_n_24hours(int(num), _get_logs)

        elif (time_unit == Unit.minutes):
            logs, _, _ = last_n_minutes(int(num), _get_logs)

    else:
        logger.info(
            f'Publishing Gmail logs from last persisted range using time unit of {unit}'
        )
        logs, start, end = last_from_persisted_windowed(
            _get_logs, 'gmail_log_fetch')

    logger.info(f'Total of {len(logs)} fetched from Gmail')
    timed_logs = list(map(with_time, logs))
    batches = partition(timed_logs, BATCH_SIZE)
    http = retryable()
    splunk_token = read_config(project_id, 'gmail')['splunk']
    for batch in batches:
        publish(http, batch, splunk_token, time_field='timestamp')

    if (len(logs) > 0):
        logger.info(f'Total of {len(logs)} persisted into Splunk from Gmail')

    if (int(num) < 0):
        event_count = len(timed_logs)
        if (event_count > 0):
            last_date = max(
                list(map(lambda event: event['timestamp'],
                         timed_logs))) / 1000.0

        else:
            last_date = None

        mark_last_fetch_windowed(start, event_count, last_date,
                                 'gmail_log_fetch')


@cli.command()
@click.option("--num", required=True)
@click.option("--unit", required=True)
def get_logs(num, unit):
    time_unit = into_unit(unit)
    if (time_unit == Unit.days):
        logs, _, _ = last_n_24hours(int(num), _get_logs)

    elif (time_unit == Unit.minutes):
        logs, _, _ = last_n_minutes(int(num), _get_logs)

    pp.pprint(logs)


@cli.command()
@click.option("--num", required=True)
@click.option("--unit", required=True)
def publish_logs(num, unit):
    _publish_gmail_logs(num, unit)


if __name__ == '__main__':
    cli()
