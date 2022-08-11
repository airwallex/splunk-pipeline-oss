#!/usr/bin/env python3
"""LastPass audit logs"""

from secops_common.logsetup import logger
from pipeline.common.splunk import publish, retryable
from pipeline.common.functional import partition
from pipeline.common.time import unix_time_millis

import json
from functools import partial

# Timestamp handling
from datetime import datetime
import pytz

# UI
import pprint
import click

pp = pprint.PrettyPrinter(indent=4)
GMT = pytz.UTC


def from_log_timestamp(created, timestamp_format):
    dt = datetime.strptime(created, timestamp_format)
    gmt_dt = GMT.localize(dt, is_dst=False)
    return unix_time_millis(gmt_dt)


def with_time(log, timestamp_field, timestamp_format):
    log['timestamp'] = from_log_timestamp(log[timestamp_field],
                                          timestamp_format)
    return log


def _publish_local_logs(filename, hec_token, timestamp_format,
                        timestamp_field):
    logs = []

    with open(filename, 'r') as f:
        logs = [json.loads(x) for x in f.readlines()]

    logger.info(f'Total of {len(logs)} fetched from local file')
    timed_logs = list(
        map(
            partial(with_time,
                    timestamp_field=timestamp_field,
                    timestamp_format=timestamp_format), logs))
    batches = partition(timed_logs, 50)
    http = retryable()
    for batch in batches:
        publish(http, batch, hec_token, time_field='timestamp')

    logger.info(f'Total of {len(logs)} persisted into Splunk')


@click.group()
def cli():
    pass


@cli.command()
@click.option("--filename", required=True)
@click.option("--hec_token", required=True)
@click.option("--timestamp_format", required=True)
@click.option("--timestamp_field", required=True)
def publish_logs(filename, hec_token, timestamp_format, timestamp_field):
    """Takes a filename containing events, each json formatted and on a new line, a HEC token, the timestamp format, 
    and the field containing the timestamp, then ingests them into Splunk"""
    _publish_local_logs(filename, hec_token, timestamp_format, timestamp_field)


if __name__ == '__main__':
    cli()
