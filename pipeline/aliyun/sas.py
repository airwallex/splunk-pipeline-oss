#!/usr/bin/env python3
""" List Aliyun VM related metrics """

from secops_common.secrets import read_config

# Aliyun
from aliyunsdkcore.acs_exception.exceptions import ClientException
from aliyunsdkcore.acs_exception.exceptions import ServerException
from aliyunsdksas.request.v20181203 import DescribeAlarmEventListRequest
from aliyunsdksas.request.v20181203 import DescribeSuspEventDetailRequest
from aliyunsdksas.request.v20181203 import DescribeAccesskeyLeakListRequest
from aliyunsdksas.request.v20181203 import DescribeExposedInstanceListRequest
from aliyunsdksas.request.v20181203 import DescribeRiskCheckResultRequest
from pipeline.common.fetch import last_n_24hours, last_n_minutes, last_from_persisted, mark_last_fetch, Unit, into_unit
from pipeline.common.time import unix_time_millis
from pipeline.aliyun.client import fetch_with_count_2, fetch_with_count_3, initialize_client, fetch_with_count, fetch_with_token, fetch_all
from datetime import datetime

# Logging
import pprint
import click

from secops_common.logsetup import logger, enable_logfile

from pipeline.common.config import CONFIG

# dedup
from pipeline.common.dedup import new_events, mark_events

from functools import partial

from pipeline.common.functional import partition

# Splunk
from pipeline.common.splunk import publish, retryable

# Caching
import functools

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


def with_source(source, m):
    m['Source'] = source
    return m


def _fetch_event(client, id):
    request = DescribeSuspEventDetailRequest.DescribeSuspEventDetailRequest()
    request.set_From('sas')
    request.set_Lang('en')
    request.set_SuspiciousEventId(id)
    return fetch_all(client, request, lambda response: response)


def _get_events(alarm, account):
    client = initialize_client(region='cn-hangzhou', account=account)
    ids = alarm['SecurityEventIds']
    if (isinstance(ids, list)):
        return list(map(partial(_fetch_event, client), ids))
    else:
        return [_fetch_event(client, ids)]


def _get_alarms(account, start, end):
    client = initialize_client(region='cn-hangzhou', account=account)
    request = DescribeAlarmEventListRequest.DescribeAlarmEventListRequest()
    request.set_From('sas')
    date_format = '%Y-%m-%d %H:%M:%S'
    request.set_TimeStart(start.strftime(date_format))
    request.set_TimeEnd(end.strftime(date_format))
    request.set_CurrentPage(0)
    request.set_Lang('en')
    return fetch_with_count_2(client, request,
                              lambda response: response['SuspEvents'])


def _get_leaks(account, start, end):
    client = initialize_client(region='cn-hangzhou', account=account)
    request = DescribeAccesskeyLeakListRequest.DescribeAccesskeyLeakListRequest(
    )
    request.set_StartTs(unix_time_millis(start))
    return fetch_with_count_3(client, request,
                              lambda response: response['AccessKeyLeakList'])


# See https://www.alibabacloud.com/help/en/security-center/latest/api-doc-sas-2018-12-03-api-doc-describeexposedinstancelist
def _get_exposed(account):
    client = initialize_client(region='cn-hangzhou', account=account)
    request = DescribeExposedInstanceListRequest.DescribeExposedInstanceListRequest(
    )
    return fetch_with_count_2(client, request,
                              lambda response: response['ExposedInstances'])


def _get_risks(account):
    client = initialize_client(region='cn-hangzhou', account=account)
    request = DescribeRiskCheckResultRequest.DescribeRiskCheckResultRequest()
    request.set_Lang('en')
    return fetch_with_count_3(client, request,
                              lambda response: response['List'])


def _fetch_exposed(account):
    exposed = _get_exposed(account)
    return list(map(partial(with_account, account), exposed))


def _fetch_risks(account):
    risks = _get_risks(account)
    return list(map(partial(with_account, account), risks))


def add_events(account, alarm):
    alarm['Events'] = _get_events(alarm, account)
    return alarm


@functools.lru_cache(maxsize=None)
def accound_id(account):
    return read_config(project_id, 'aliyun')[account]['id']


def with_account(account, m):
    m['CloudAccountId'] = accound_id(account)
    return m


def _get_alert_id(event):
    return event['AlarmUniqueInfo']


def _fetch_alerts(num, unit, account):
    time_unit = into_unit(unit)

    if (time_unit == Unit.days):
        alarms, _, _ = last_n_24hours(int(num), partial(_get_alarms, account))

    elif (time_unit == Unit.minutes):
        alarms, _, _ = last_n_minutes(int(num), partial(_get_alarms, account))

    inc_account = list(map(partial(with_account, account), alarms))
    with_events = list(map(partial(add_events, account), inc_account))
    new = new_events(with_events, _get_alert_id, 'aliyun_sas_log_dedup')

    logger.info(
        f'Total of {len(alarms)} fetched from Aliyn out of which {len(new)} are new'
    )

    return new


def _get_leak_id(event):
    return event['Id']


def _fetch_leaks(num, unit, account):
    time_unit = into_unit(unit)

    if (time_unit == Unit.days):
        leaks, _, _ = last_n_24hours(int(num), partial(_get_leaks, account))

    elif (time_unit == Unit.minutes):
        leaks, _, _ = last_n_minutes(int(num), partial(_get_leaks, account))

    new = new_events(leaks, _get_leak_id, 'aliyun_sas_leaks_log_dedup')
    inc_account = list(map(partial(with_account, account), new))

    logger.info(
        f'Total of {len(leaks)} leaks fetched from Aliyn out of which {len(new)} are new'
    )

    return inc_account


def _get_alarm_id(event):
    return event['AlarmUniqueInfo']


def _publish_sas_alerts(num, unit, account):
    new = _fetch_alerts(num, unit, account)
    sourced = list(map(partial(with_source, 'aliyun:sas:alerts'), new))
    batches = partition(sourced, BATCH_SIZE)

    http = retryable()
    splunk_token = read_config(project_id, 'aliyun_sas')['splunk']
    for batch in batches:
        publish(http, batch, splunk_token, sourcetype_field='Source')

    if (len(new) > 0):
        logger.info(
            f'Total of {len(new)} alerts persisted into Splunk from Aliyun SAS'
        )

    mark_events(new, _get_alarm_id, 'aliyun_sas_log_dedup')


def _publish_sas_leaks(num, unit, account):
    new = _fetch_leaks(num, unit, account)
    sourced = list(map(partial(with_source, 'aliyun:sas:key_leaks'), new))
    batches = partition(new, BATCH_SIZE)

    http = retryable()
    splunk_token = read_config(project_id, 'aliyun_sas')['splunk']
    for batch in batches:
        publish(http, batch, splunk_token, sourcetype_field='Source')

    if (len(new) > 0):
        logger.info(
            f'Total of {len(new)} leaks persisted into Splunk from Aliyun SAS')

    mark_events(new, _get_leak_id, 'aliyun_sas_leaks_log_dedup')


def _publish_sas_exposed(account):
    new = _fetch_exposed(account)
    sourced = list(map(partial(with_source, 'aliyun:sas:exposed_assets'), new))
    batches = partition(sourced, BATCH_SIZE)

    http = retryable()
    splunk_token = read_config(project_id, 'aliyun_sas')['splunk']
    for batch in batches:
        publish(http, batch, splunk_token, sourcetype_field='Source')

    logger.info(
        f'Total of {len(new)} exposed instances persisted into Splunk from Aliyun SAS'
    )


def _publish_sas_risks(account):
    new = _fetch_exposed(account)
    sourced = list(map(partial(with_source, 'aliyun:sas:config'), new))
    batches = partition(sourced, BATCH_SIZE)

    http = retryable()
    splunk_token = read_config(project_id, 'aliyun_sas')['splunk']
    for batch in batches:
        publish(http, batch, splunk_token, sourcetype_field='Source')

    logger.info(
        f'Total of {len(new)} risk items persisted into Splunk from Aliyun SAS'
    )


def _publish_sas(num, unit, _type, account):
    if _type == 'alerts':
        _publish_sas_alerts(num, unit, account)
    elif _type == 'leaks':
        _publish_sas_leaks(num, unit, account)
    elif _type == 'exposed':
        _publish_sas_exposed(account)
    elif _type == 'risks':
        _publish_sas_risks(account)
    else:
        raise Exception('no matching sas type found')


@cli.command()
@click.option("--num", required=True)
@click.option("--unit", required=True)
@click.option("--account", required=True)
def get_alerts(num, unit, account):
    alerts = _fetch_alerts(num, unit, account)
    for alert in alerts:
        pp.pprint(alert)


@cli.command()
@click.option("--num", required=True)
@click.option("--unit", required=True)
@click.option("--account", required=True)
def get_leaks(num, unit, account):
    leaks = _fetch_leaks(num, unit, account)
    for leak in leaks:
        pp.pprint(leak)


@cli.command()
@click.option("--account", required=True)
def get_exposed(account):
    instances = _fetch_exposed(account)
    for instance in instances:
        pp.pprint(instance)


@cli.command()
@click.option("--account", required=True)
def get_risks(account):
    items = _fetch_risks(account)
    for item in items:
        pp.pprint(item)


@cli.command()
@click.option("--num", required=True)
@click.option("--unit", required=True)
def publish_alerts(num, unit):
    _publish_sas_alerts(num, unit)


@cli.command()
@click.option("--num", required=True)
@click.option("--unit", required=True)
@click.option("--account", required=True)
def publish_leaks(num, unit, account):
    _publish_sas_leaks(num, unit)


@cli.command()
@click.option("--account", required=True)
def publish_exposed(account):
    _publish_sas_exposed(account)


@cli.command()
@click.option("--account", required=True)
def publish_risks(account):
    _publish_sas_risks(account)


if __name__ == '__main__':
    cli()
