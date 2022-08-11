#!/usr/bin/env python3
"""Uploading a Google drive spreadsheet into a Splunk index"""

from secops_common.secrets import read_config
from secops_common.logsetup import logger
from pipeline.common.google import creds
from pipeline.common.splunk import publish, retryable

from pipeline.common.config import CONFIG

# Bigquery
import pipeline.common.bigquery
from secops_common.bigquery import latest_rows, get_table, insert_rows

from pipeline.common.time import unix_time_millis

from pipeline.common.functional import partition

from googleapiclient.discovery import build

# UI
import pprint
import click

from datetime import datetime, timedelta, timezone

# checksum
import hashlib

from functools import reduce

pp = pprint.PrettyPrinter(indent=4)

project_id = CONFIG['project_id']

splunk_token = read_config(project_id, 'spreadsheet')['splunk']

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']


def _read_spreadsheet(_id, _range):
    service = build('sheets', 'v4', credentials=creds(SCOPES))
    sheet = service.spreadsheets()
    hashlib.md5("".encode('utf-8')).hexdigest()
    result = sheet.values().get(spreadsheetId=_id, range=_range).execute()
    return result.get('values', [])


def md5(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()


def _checksum(rows):
    return reduce(lambda acc, row: md5(acc + md5(','.join(row))), rows, '')


def last_from_persisted(_id):
    # Making sure table is set
    get_table('spreadsheet_tracking')
    rows = latest_rows('spreadsheet_tracking')
    if (rows.total_rows == 0):
        return (_id, '', None)
    else:
        return tuple(list(next(rows.pages))[0])


def range_len(_range):
    """the number of columnns in the range"""
    return ord(_range.split(':')[1]) - 64


def fail_on_non_matching_rows(rows, _range):
    expected = range_len(_range)
    non_matching = list(filter(lambda row: len(row) != expected, rows))
    if (len(non_matching)):
        raise Exception(
            f'some rows have missing values for the provided range {_range}, please fix the spreadsheet'
        )


def _publish_spreadsheet(_id, _range):
    (_, prev_sum, _) = last_from_persisted(_id)
    now = unix_time_millis(datetime.now(tz=timezone.utc))
    rows = _read_spreadsheet(_id, _range)
    curr_sum = _checksum(rows)
    fail_on_non_matching_rows(rows, _range)
    if (curr_sum != prev_sum):
        logger.info(
            f'spreadsheet {_id} has changed, publishing changes to Splunk')
        meta = rows.pop(0) + ['created']
        events = list(map(lambda row: dict(zip(meta, row + [now])), rows))
        http = retryable()
        batches = partition(events, 50)
        for batch in batches:
            publish(http, batch, splunk_token, time_field='created')

        stamp = datetime.now(tz=timezone.utc)
        insert_rows([[_id, curr_sum, stamp]], 'spreadsheet_tracking')
    else:
        logger.info(
            f'spreadsheet {_id} didnt changed skipping publishing changes to splunk'
        )


@click.group()
def cli():
    pass


@cli.command()
@click.option("--id", required=True)
@click.option("--range", required=True)
def read_spreadsheet(id, range):
    rows = _read_spreadsheet(id, range)
    pp.pprint(_checksum(rows))
    pp.pprint(rows)


@cli.command()
@click.option("--id", required=True)
@click.option("--range", required=True)
def publish_spreadsheet(id, range):
    _publish_spreadsheet(id, range)


if __name__ == '__main__':
    cli()
