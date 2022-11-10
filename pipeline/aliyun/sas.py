#!/usr/bin/env python3
""" List Aliyun VM related metrics """

# Aliyun
from aliyunsdkcore.acs_exception.exceptions import ClientException
from aliyunsdkcore.acs_exception.exceptions import ServerException
from aliyunsdksas.request.v20181203 import DescribeAlarmEventListRequest
from aliyunsdkecs.request.v20140526 import DescribeInstancesRequest
from pipeline.common.fetch import last_n_24hours, last_n_minutes, last_from_persisted, mark_last_fetch, Unit, into_unit

# Logging
import pprint
import click

from secops_common.logsetup import logger, enable_logfile

# Aliyun
from pipeline.aliyun.client import fetch_with_count_2, initialize_client, fetch_with_count, fetch_with_token
from datetime import datetime

from functools import partial

pp = pprint.PrettyPrinter(indent=4)


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


def _get_alarms(start, end):
    client = initialize_client(region='cn-hangzhou')
    request = DescribeAlarmEventListRequest.DescribeAlarmEventListRequest()
    request.set_From('sas')
    date_format = '%Y-%d-%m %H:%M:%S'
    request.set_TimeStart(start.strftime(date_format))
    request.set_TimeEnd(end.strftime(date_format))
    request.set_CurrentPage(0)
    return fetch_with_count_2(client, request,
                              lambda response: response['SuspEvents'])

@cli.command()
@click.option("--num", required=True)
@click.option("--unit", required=True)
def get_alarms(num, unit):
    time_unit = into_unit(unit)

    if (time_unit == Unit.days):
         logs, _, _ = last_n_24hours(int(num), _get_alarms)

    elif (time_unit == Unit.minutes):
         logs, _, _ = last_n_minutes(int(num), _get_alarms)

    for log in logs:
        print(log)

    logger.info(f'Total of {len(logs)} fetched from Aliyn')


if __name__ == '__main__':
    cli()
