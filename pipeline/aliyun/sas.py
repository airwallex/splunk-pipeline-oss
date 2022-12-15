#!/usr/bin/env python3
""" List Aliyun VM related metrics """

from secops_common.secrets import read_config

# Aliyun
from aliyunsdkcore.acs_exception.exceptions import ClientException
from aliyunsdkcore.acs_exception.exceptions import ServerException
from aliyunsdksas.request.v20181203 import DescribeAlarmEventListRequest
from aliyunsdksas.request.v20181203 import DescribeSuspEventDetailRequest
from pipeline.common.fetch import last_n_24hours, last_n_minutes, last_from_persisted, mark_last_fetch, Unit, into_unit

# Logging
import pprint
import click

from secops_common.logsetup import logger, enable_logfile

from pipeline.common.config import CONFIG

# Aliyun
from pipeline.aliyun.client import fetch_with_count_2, initialize_client, fetch_with_count, fetch_with_token, fetch_all
from datetime import datetime

# dedup
from pipeline.common.dedup import new_events, mark_events

from functools import partial

from pipeline.common.functional import partition

# Splunk
from pipeline.common.splunk import publish, retryable

pp = pprint.PrettyPrinter(indent=4)

BATCH_SIZE = 5000
project_id = CONFIG['project_id']


@click.group()
def cli():
    pass


def vuln_row(stamp, level, vuln):
    extended = vuln['ExtendContentJson']
    return [
        vuln['InstanceName'], vuln['Level'], vuln['Related'],
        vuln['InternetIp'], vuln['IntranetIp'], extended['Os'],
        extended['OsRelease'], level, stamp
    ]


def _fetch_event(client, id):
    request = DescribeSuspEventDetailRequest.DescribeSuspEventDetailRequest()
    request.set_From('sas')
    request.set_Lang('en')
    request.set_SuspiciousEventId(id)
    return fetch_all(client, request, lambda response: response)


def _get_events(alarm):
    client = initialize_client(region='cn-hangzhou')
    ids = alarm['SecurityEventIds']
    if (isinstance(ids, list)):
        return list(map(partial(_fetch_event, client), ids))
    else:
        return [_fetch_event(client, ids)]


def _get_alarms(start, end):
    client = initialize_client(region='cn-hangzhou')
    request = DescribeAlarmEventListRequest.DescribeAlarmEventListRequest()
    request.set_From('sas')
    date_format = '%Y-%m-%d %H:%M:%S'
    request.set_TimeStart(start.strftime(date_format))
    request.set_TimeEnd(end.strftime(date_format))
    request.set_CurrentPage(0)
    return fetch_with_count_2(client, request,
                              lambda response: response['SuspEvents'])


def add_events(alarm):
    alarm['Events'] = _get_events(alarm)
    return alarm


def _get_id(event):
    return event['AlarmUniqueInfo']


def _fetch(num, unit):
    time_unit = into_unit(unit)

    if (time_unit == Unit.days):
        alarms, _, _ = last_n_24hours(int(num), _get_alarms)

    elif (time_unit == Unit.minutes):
        alarms, _, _ = last_n_minutes(int(num), _get_alarms)

    with_events = list(map(add_events, alarms))
    new = new_events(with_events, _get_id, 'aliyun_sas_log_dedup')

    logger.info(
        f'Total of {len(alarms)} fetched from Aliyn out of which {len(new)} are new'
    )

    return new


def _publish_sas_alarms(num, unit):
    new = _fetch(num, unit)
    batches = partition(new, BATCH_SIZE)

    http = retryable()
    splunk_token = read_config(project_id, 'aliyun_sas')['splunk']
    for batch in batches:
        publish(http, batch, splunk_token)

    if (len(new) > 0):
        logger.info(
            f'Total of {len(new)} persisted into Splunk from Aliyun SAS')

    mark_events(new, _get_id, 'aliyun_sas_log_dedup')


@cli.command()
@click.option("--num", required=True)
@click.option("--unit", required=True)
def get_alarms(num, unit):
    alerts = _fetch(num, unit)
    for alert in alerts:
        print(alert)


@cli.command()
@click.option("--num", required=True)
@click.option("--unit", required=True)
def publish_alarms(num, unit):
    _publish_sas_alarms(num, unit)


if __name__ == '__main__':
    cli()
