#!/usr/bin/env python3
"""Confluence audit logs"""

from secops_common.secrets import read_config
from secops_common.logsetup import logger, enable_logfile
from pipeline.common.splunk import publish, retryable
from pipeline.common.functional import partition
from pipeline.common.time import unix_time_millis
from pipeline.common.fetch import last_n_24hours, last_n_minutes, Unit, into_unit

from pipeline.common.window import last_from_persisted_windowed, mark_last_fetch_windowed

import requests

# Timestamp handling
from datetime import datetime
import pytz

# UI
import pprint
import click

# Units
from enum import Enum, auto

from pipeline.common.config import CONFIG

pp = pprint.PrettyPrinter(indent=4)

project_id = CONFIG['project_id']
token = read_config(project_id, 'confluence')['token']
splunk_token = read_config(project_id, 'confluence')['splunk']
user = read_config(project_id, 'confluence')['user']
LIMIT = 1000

company = CONFIG['company']


@click.group()
def cli():
    pass


base = f'https://{company}.atlassian.net/wiki'
headers = {'Accept': 'application/json'}


def get_result(response):
    if (response == None):
        return None
    elif (response.status_code != 200):
        return None
    else:
        return response.json()['results']


def next_page(response, params):
    data = response.json()
    if ('next' in data['_links']):
        _next = data['_links']['next']
        response = requests.get(base + _next,
                                headers=headers,
                                auth=(user, token),
                                params=params)
        return response
    else:
        return None


def _get_logs(start, end):

    logger.debug(f'Getting logs from confluence for {start} - {end}')
    url = base + '/rest/api/audit'
    params = {
        'startDate': unix_time_millis(start),
        'endDate': unix_time_millis(end)
    }
    results = []
    response = requests.get(url,
                            headers=headers,
                            auth=(user, token),
                            params=params)
    result = get_result(response)
    if (result != None):
        results.extend(result)

    while (result != None):
        response = next_page(response, params)
        result = get_result(response)
        if (result != None):
            results.extend(result)

    logger.debug(
        f'Total of {len(results)} logs fetched in _get_logs Confluence')
    return results


def readable_date(event):
    ts = event['creationDate'] / 1000
    event['creationDate'] = datetime.fromtimestamp(ts).strftime(
        "%B %d, %Y - %H:%m:%S")
    return event


def _publish_confluence_logs(num, unit):
    time_unit = into_unit(unit)
    if (int(num) > 0):
        logger.info(f'Publishing Confluence logs for {num} {unit}')
        if (time_unit == Unit.days):
            logs, _, _ = last_n_24hours(int(num), _get_logs)

        elif (time_unit == Unit.minutes):
            logs, _, _ = last_n_minutes(int(num), _get_logs)

    else:
        logger.info(
            f'Publishing Confluence logs from last persisted range using time unit of {unit}'
        )
        logs, start, end = last_from_persisted_windowed(
            _get_logs, 'confluence_log_fetch')

    logger.info(f'Total of {len(logs)} fetched from Confluence')
    batches = partition(logs, 50)
    http = retryable()
    for batch in batches:
        publish(http, batch, splunk_token, time_field='creationDate')

    if (len(logs) > 0):
        logger.info(
            f'Total of {len(logs)} persisted into Splunk from Confluence')

    if (int(num) < 0):
        event_count = len(logs)
        if (event_count > 0):
            last_date = max(
                list(map(lambda event: event['creationDate'], logs))) / 1000.0

        else:
            last_date = None

        mark_last_fetch_windowed(start, event_count, last_date,
                                 'confluence_log_fetch')


@cli.command()
@click.option("--num", required=True)
@click.option("--unit", required=True)
def publish_logs(num, unit):
    _publish_confluence_logs(num, unit)


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

        logs = list(map(readable_date, logs))

    else:
        logs, start, end = last_from_persisted_windowed(
            _get_logs, 'confluence_log_fetch')

    logger.info(f'Total of {len(logs)} fetched from Confluence')


if __name__ == '__main__':
    cli()
