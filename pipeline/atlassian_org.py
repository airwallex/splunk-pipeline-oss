#!/usr/bin/env python3
"""Atlassian audit logs"""

from secops_common.secrets import read_config
from secops_common.logsetup import logger
from pipeline.common.splunk import publish, retryable
from pipeline.common.functional import partition
from pipeline.common.time import unix_time_millis
from pipeline.common.fetch import last_n_24hours, last_n_minutes, last_from_persisted, mark_last_fetch, Unit, into_unit

import requests
import math

# Timestamp handling
from datetime import datetime, timedelta, timezone

# UI
import pprint
import click

from pipeline.common.config import CONFIG

project_id = CONFIG['project_id']

pp = pprint.PrettyPrinter(indent=4)

token = read_config(project_id, 'atlassian')['token']
splunk_token = read_config(project_id, 'atlassian')['splunk']
# Generated with the token
org_id = read_config(project_id, 'atlassian')['org_id']
LIMIT = 1000

headers = {'Accept': 'application/json', 'Authorization': f'Bearer {token}'}
url = f'https://api.atlassian.com/admin/v1/orgs/{org_id}/events'


def get_results(response):
    if response == None:
        return None
    elif response.status_code != 200:
        logger.warning(f'Received {response.status_code} from API')
        return None
    else:
        return response.json()


def into_atlassian_date(dt):
    return math.floor(dt.timestamp() * 1000)


def from_atlassian_date(created):
    stamp = created.split('.')[0]

    # occassionally Atlassian drops the milliseconds - light hack
    if not stamp.endswith('Z'):
        stamp += 'Z'

    return unix_time_millis(
        datetime.strptime(stamp,
                          '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc))


def _get_atlassian_audit_logs(params):
    logger.info(f'Getting instance audit events')
    response = requests.get(url, headers=headers, params=params)
    logger.info(f'Getting first page for {url}...')
    json_resp = get_results(response)

    if not json_resp:
        return []

    curr_results = json_resp['data']
    logger.debug(f'Got {len(curr_results)} results')

    results = curr_results
    next_url = json_resp['links'].get('next')

    while next_url:
        logger.info('Getting page at {}...'.format(next_url))

        response = requests.get(next_url, headers=headers, params=params)
        json_resp = get_results(response)
        curr_results = json_resp['data']
        next_url = json_resp['links'].get('next')
        logger.info(f'Got {len(curr_results)} results')

        results.extend(curr_results)

    return results


def _get_logs(start, end):
    logger.info(f'Getting logs from atlassian for {start} - {end}')
    params = {
        'from': into_atlassian_date(start),
        'to': into_atlassian_date(end),
    }
    results = _get_atlassian_audit_logs(params)

    logger.debug(
        f'Total of {len(results)} logs fetched in _get_logs Atlassian')
    return results


def with_time(log):
    log['timestamp'] = from_atlassian_date(log['attributes']['time'])
    return log


def _publish_atlassian_logs(num, unit):
    time_unit = into_unit(unit)
    if int(num) > 0:
        logger.info(f'Publishing Atlassian logs for {num} {unit}')
        if time_unit == Unit.days:
            logs, _, _ = last_n_24hours(int(num), _get_logs)

        elif time_unit == Unit.minutes:
            logs, _, _ = last_n_minutes(int(num), _get_logs)

    else:
        logger.info(
            f'Publishing Atlassian logs from last persisted range using time unit of {unit}'
        )
        logs, start, end = last_from_persisted(time_unit, _get_logs,
                                               'atlassian_log_fetch')

    logger.info(f'Total of {len(logs)} fetched from Atlassian')
    timed_logs = list(map(with_time, logs))
    batches = partition(timed_logs, 50)
    http = retryable()
    for batch in batches:
        publish(http, batch, splunk_token, time_field='timestamp')

    if (len(logs) > 0):
        logger.info(
            f'Total of {len(logs)} persisted into Splunk from Atlassian')

    if int(num) < 0:
        mark_last_fetch(start, end, True, 'atlassian_log_fetch')


@click.group()
def cli():
    pass


@cli.command()
@click.option("--num", required=True)
@click.option("--unit", required=True)
def get_logs(num, unit):
    time_unit = into_unit(unit)
    if time_unit == Unit.days:
        logs, _, _ = last_n_24hours(int(num), _get_logs)

    elif time_unit == Unit.minutes:
        logs, _, _ = last_n_minutes(int(num), _get_logs)

    pp.pprint(logs)


@cli.command()
@click.option("--num", required=True)
@click.option("--unit", required=True)
def publish_logs(num, unit):
    _publish_atlassian_logs(num, unit)


if __name__ == '__main__':
    cli()
