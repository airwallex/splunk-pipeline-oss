#!/usr/bin/env python3
"""Google workspace logs"""

# Common functions
from pipeline.common.config import CONFIG
from secops_common.misc import serialize, file_deserialize
from secops_common.secrets import read_config
from secops_common.logsetup import logger
from secops_common.functional import compose2

from pipeline.common.google import creds
from googleapiclient.discovery import build

from pipeline.common.time import unix_time_millis
from pipeline.common.functional import partition

# Bigquery
from pipeline.common.bigquery import AUDITS
from secops_common.bigquery import delete_table_and_view

from dateutil import parser

# UI
import pprint
import click

# publishing to splunk
from pipeline.common.splunk import publish, retryable

from pipeline.common.fetch import last_n_24hours, last_n_minutes, Unit, into_unit

from pipeline.common.window import last_from_persisted_windowed, mark_last_fetch_windowed

from functools import partial

from google.oauth2 import service_account

import time

pp = pprint.PrettyPrinter(indent=4)

subject = CONFIG['subject']

project_id = CONFIG['project_id']

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/admin.reports.audit.readonly']


@click.group()
def cli():
    pass


def get_activities(service, type, start, end, token=None, attempt=0):
    if (attempt > 10):
        raise Exception(f'Failed to get activities for {attempt} times')

    try:
        return service.activities().list(userKey='all',
                                         applicationName=type,
                                         startTime=start.isoformat(),
                                         endTime=end.isoformat(),
                                         pageToken=token).execute()
    except Exception as e:
        logger.info(f'failed to fetch activities due to {e} retry {attempt}')
        time.sleep(1)
        return get_activities(service, type, start, end, token, attempt + 1)


def _get_logs(type, start, end):
    logger.info(
        f'Getting logs from Google workspace {type} for {start} - {end}')
    info = read_config(project_id, 'service_info')
    cs = service_account.Credentials.from_service_account_info(info,
                                                               scopes=SCOPES,
                                                               subject=subject)
    service = build('admin', 'reports_v1', credentials=cs)
    activities = get_activities(service, type, start, end)
    results = activities.get('items', [])
    token = activities.get('nextPageToken', None)

    while (token != None):
        activities = get_activities(service, type, start, end, token)
        results.extend(activities.get('items', []))
        token = activities.get('nextPageToken', None)

    logger.debug(
        f'Total of {len(results)} logs fetched in _get_logs Google Workspace {type}'
    )
    return results


def _write_activities(file_object, activities):
    for activity in activities.get('items', []):
        file_object.write(serialize(activity))
        file_object.write('\n')


def _persist_logs(type, start, end):
    file_object = open('logs.json', 'a')
    info = read_config(project_id, 'service_info')
    cs = service_account.Credentials.from_service_account_info(info,
                                                               scopes=SCOPES,
                                                               subject=subject)
    service = build('admin', 'reports_v1', credentials=cs)
    activities = get_activities(service, type, start, end)
    _write_activities(file_object, activities)
    token = activities.get('nextPageToken', None)

    while (token != None):
        activities = get_activities(service, type, start, end, token)
        _write_activities(file_object, activities)
        token = activities.get('nextPageToken', None)

    file_object.close()


def with_time(log):
    log['timestamp'] = unix_time_millis(parser.parse((log['id']['time'])))
    return log


BATCH_SIZE = 5000


def _publish_workspace_logs(num, unit, type):
    time_unit = into_unit(unit)
    if (int(num) > 0):
        logger.info(
            f'Publishing Google workspace logs for {num} {unit} {type}')
        if (time_unit == Unit.days):
            logs, _, _ = last_n_24hours(int(num), partial(_get_logs, type))

        elif (time_unit == Unit.minutes):
            logs, _, _ = last_n_minutes(int(num), partial(_get_logs, type))

    else:
        logger.info(f'Fetching last persisted logs from window for {type}')
        logs, start, end = last_from_persisted_windowed(
            partial(_get_logs, type), f'workspace_{type}_log_fetch')

    logger.info(
        f'Total of {len(logs)} fetched from Google workspace {type} for {start} - {end} range'
    )

    timed_logs = list(map(with_time, logs))
    batches = partition(timed_logs, BATCH_SIZE)
    http = retryable()
    splunk_token = read_config(project_id,
                               f'google_workspace_{type}')['splunk']
    for batch in batches:
        publish(http, batch, splunk_token, time_field='timestamp')

    logger.info(
        f'Total of {len(logs)} persisted into Splunk from Google workspaces {type} using provided time range'
    )

    if (int(num) < 0):

        event_count = len(timed_logs)
        if (event_count > 0):
            last_date = max(
                list(map(lambda event: event['timestamp'],
                         timed_logs))) / 1000.0

        else:
            last_date = None

        mark_last_fetch_windowed(start, event_count, last_date,
                                 f'workspace_{type}_log_fetch')


@cli.command()
@click.option("--num", required=True)
@click.option("--unit", required=True)
@click.option("--type", required=True)
def publish_logs(num, unit, type):
    _publish_workspace_logs(num, unit, type)


@cli.command()
def purge_all():
    for audit in AUDITS:
        delete_table_and_view(f'workspace_{audit}_log_fetch')


@cli.command()
@click.option("--type", required=True)
def purge_single(type):
    delete_table_and_view(f'workspace_{type}_log_fetch')


from itertools import islice


@cli.command()
@click.option("--type", required=True)
@click.option("--file", required=True)
def publish_file(type, file):
    """ Persisting large sized files (multi GB in size) into Splunk """
    splunk_token = read_config(project_id,
                               f'google_workspace_{type}')['splunk']
    http = retryable()
    total = 0
    n = BATCH_SIZE
    with open(file, 'rb') as f:
        for lines in iter(lambda: tuple(islice(f, n)), ()):
            try:
                batch = list(map(compose2(with_time, file_deserialize), lines))
                publish(http, batch, splunk_token, time_field='timestamp')
                total += len(lines)
                logger.info(
                    f'Total of {total} logs were persisted into Splunk')
            except Exception as e:
                for line in lines:
                    print(line)
                    print(file_deserialize(line))
                raise SystemExit(1)


@cli.command()
@click.option("--type", required=True)
@click.option("--num", required=True)
@click.option("--unit", required=True)
def persist_logs(type, num, unit):
    info = read_config(project_id, 'service_info')
    cs = service_account.Credentials.from_service_account_info(info,
                                                               scopes=SCOPES,
                                                               subject=subject)
    service = build('admin', 'reports_v1', credentials=cs)
    time_unit = into_unit(unit)
    if (time_unit == Unit.days):
        last_n_24hours(int(num), partial(_persist_logs, type))

    elif (time_unit == Unit.minutes):
        last_n_minutes(int(num), partial(_persist_logs, type))


@cli.command()
@click.option("--type", required=True)
@click.option("--num", required=True)
@click.option("--unit", required=True)
def get_logs(type, num, unit):
    info = read_config(project_id, 'service_info')
    cs = service_account.Credentials.from_service_account_info(info,
                                                               scopes=SCOPES,
                                                               subject=subject)
    service = build('admin', 'reports_v1', credentials=cs)
    time_unit = into_unit(unit)

    if (int(num) > 0):
        if (time_unit == Unit.days):
            logs, _, _ = last_n_24hours(int(num), partial(_get_logs, type))

        elif (time_unit == Unit.minutes):
            logs, _, _ = last_n_minutes(int(num), partial(_get_logs, type))

    else:
        logger.info(f'Fetching last persisted logs from window for {type}')
        logs, start, end = last_from_persisted_windowed(
            partial(_get_logs, type), f'workspace_{type}_log_fetch')

    logger.info(
        f'Total of {len(logs)} fetched from Google workspace {type} for {start} - {end} range'
    )


if __name__ == '__main__':
    cli()
