#!/usr/bin/env python3
""" Bamboo Employee data k/v store  """

import datetime
import pytz
import requests
from requests.auth import HTTPBasicAuth

# UI
import pprint
import click

from secops_common.secrets import read_config
from secops_common.misc import serialize

# Splunk KV
from pipeline.common.splunk import insert_batch_kv, empty_collection, retryable, publish

from pipeline.common.functional import partition

from secops_common.logsetup import logger

from pipeline.common.config import CONFIG

from functools import reduce, partial
from secops_common.functional import merge, compose2

pp = pprint.PrettyPrinter(indent=4)

project_id = CONFIG['project_id']

bamboo_token = read_config(project_id, 'bamboo')['token']

splunk_api_token = read_config(project_id, 'splunk_api')['token']

splunk_token = read_config(project_id, 'bamboo')['splunk']

import importlib

transform_logic = importlib.util.find_spec('internal.bamboo')

if (transform_logic is not None):
    from internal.bamboo import transform
else:
    transform = None


@click.group()
def cli():
    pass


headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}

company = CONFIG['company']

base_url = f'https://api.bamboohr.com/api/gateway.php/{company}'


def _fetch():
    reports_endpoint = '/v1/reports/custom'
    data = {
        "fields": [
            "id", "employeeNumber", "workEmail", "firstName", "lastName",
            "displayName", "location", "jobTitle", "department", "division",
            "supervisor", "employmentHistoryStatus", "hireDate",
            "terminationDate"
        ]
    }
    response = requests.post(base_url + reports_endpoint,
                             headers=headers,
                             data=serialize(data),
                             auth=HTTPBasicAuth(bamboo_token, 'x'))

    employees = response.json()['employees']

    if (transform is not None):
        return transform(employees)
    else:
        return employees


def _process(records, destination):
    http = retryable()

    if destination == 'kv_store':
        logger.info('Emptying kv_hr_info')
        empty_collection(http, 'kv_hr_info', splunk_api_token)
        batches = partition(list(records), 100)
        logger.info(f'Populating kv_hr_info')

        for batch in batches:
            insert_batch_kv(http, 'kv_hr_info', batch, splunk_api_token)
    elif destination == 'hec':
        batches = partition(list(records), 500)
        logger.info(f'Ingesting logs through HEC')

        for batch in batches:
            publish(http, batch, splunk_token)

    logger.info(f'Total of {len(records)} persisted into Splunk from Bamboo')


@cli.command()
def fetch():
    pp.pprint(list(_fetch()))


def _publish_and_download_bamboo(destination):
    _process(list(_fetch()), destination)


@cli.command()
@click.option("--destination", required=True)
def process(destination):
    _publish_and_download_bamboo(destination)


if __name__ == '__main__':
    cli()
