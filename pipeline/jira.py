#!/usr/bin/env python3
"""Jira audit logs"""

from secops_common.logsetup import logger, enable_logfile
from secops_common.secrets import read_config
from pipeline.common.splunk import publish, retryable
from pipeline.common.functional import partition
from pipeline.common.time import unix_time_millis
from pipeline.common.fetch import last_n_24hours, last_n_minutes, last_from_persisted, mark_last_fetch, Unit, into_unit
from pipeline.common.window import last_from_persisted_windowed, mark_last_fetch_windowed

from secops_common.bigquery import delete_table_and_view

from pipeline.common.config import CONFIG

import requests

# Timestamp handling
from datetime import datetime, timezone
import pytz

# UI
import pprint
import click

# Units
from enum import Enum, auto

company = CONFIG['company']

pp = pprint.PrettyPrinter(indent=4)

project_id = CONFIG['project_id']

user = read_config(project_id, 'jira')['user']
token = read_config(project_id, 'jira')['token']
splunk_token = read_config(project_id, 'jira')['splunk']
LIMIT = 1000


@click.group()
def cli():
    pass


base = f'https://{company}.atlassian.net'
headers = {'Accept': 'application/json'}
url = base + '/rest/api/3/auditing/record'


def get_result(response):
    if (response == None):
        return None
    elif (response.status_code != 200):
        return None
    else:
        return response.json()['records']


def next_page(response, params, index):
    data = response.json()
    if (len(data['records']) == data['limit']):
        params['offset'] = params['limit'] * index
        return requests.get(url,
                            headers=headers,
                            auth=(user, token),
                            params=params)
    else:
        return None


def into_jira_date(dt):
    return "%s:%.3f%s" % (dt.strftime('%Y-%m-%dT%H:%M'),
                          float("%.3f" % (dt.second + dt.microsecond / 1e6)),
                          dt.strftime('%z'))


def from_jira_date(created):
    stamp = created.split('.')[0]
    return unix_time_millis(
        datetime.strptime(stamp,
                          '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc))


def _get_logs(start, end):
    logger.debug(f'Getting logs from Jira for {start} - {end}')
    params = {
        'from': into_jira_date(start),
        'to': into_jira_date(end),
        'limit': 1000,
        'offset': 0
    }
    results = []
    idx = 1
    response = requests.get(url,
                            headers=headers,
                            auth=(user, token),
                            params=params)
    result = get_result(response)
    if (result != None):
        results.extend(result)

    while (result != None):
        response = next_page(response, params, idx)
        result = get_result(response)
        if (result != None):
            idx += 1
            results.extend(result)

    logger.debug(f'Total of {len(results)} logs fetched in _get_logs Jira')
    return results


def with_time(log):
    log['timestamp'] = from_jira_date(log['created'])
    return log


def _publish_jira_logs(num, unit):
    time_unit = into_unit(unit)
    if (int(num) > 0):
        logger.info(f'Publishing Jira logs for {num} {unit}')
        if (time_unit == Unit.days):
            logs, _, _ = last_n_24hours(int(num), _get_logs)

        elif (time_unit == Unit.minutes):
            logs, _, _ = last_n_minutes(int(num), _get_logs)

    else:
        logger.info(
            f'Publishing Jira logs from last persisted range using time unit of {unit}'
        )
        logs, start, end = last_from_persisted_windowed(
            _get_logs, 'jira_log_fetch')

    logger.info(f'Total of {len(logs)} fetched from Jira')
    timed_logs = list(map(with_time, logs))
    batches = partition(timed_logs, 50)
    http = retryable()
    for batch in batches:
        publish(http, batch, splunk_token, time_field='timestamp')

    if (len(logs) > 0):
        logger.info(f'Total of {len(logs)} persisted into Splunk from Jira')

    if (int(num) < 0):
        event_count = len(logs)
        if (event_count > 0):
            last_date = max(
                list(map(lambda event: from_jira_date(event['created']),
                         logs))) / 1000.0

        else:
            last_date = None

        mark_last_fetch_windowed(start, event_count, last_date,
                                 'jira_log_fetch')


@cli.command()
@click.option("--num", required=True)
@click.option("--unit", required=True)
def publish_logs(num, unit):
    _publish_jira_logs(num, unit)


@cli.command()
def purge():
    delete_table_and_view('jira_log_fetch')


@cli.command()
@click.option("--num", required=True)
@click.option("--unit", required=True)
def get_logs(num, unit):
    time_unit = into_unit(unit)

    if (int(num) > 0):
        if (time_unit == Unit.days):
            logs, _, _ = last_n_24hours(int(num), _get_logs)

        elif (time_unit == Unit.minutes):
            logs, _, _ = last_n_minutes(int(num), _get_logs)

    else:
        logs, start, end = last_from_persisted_windowed(
            _get_logs, 'jira_log_fetch')

    logger.info(f'Total of {len(logs)} fetched from Jira')


if __name__ == '__main__':
    cli()
