import pprint
import click

from pipeline.snipeit.helper import SnipeIT, DEFAULT_RESULT_LIMIT

import uuid
from datetime import datetime, timezone
from functools import partial

from secops_common.secrets import read_config
from secops_common.logsetup import logger
from secops_common.functional import flatten
from pipeline.common.splunk import publish, retryable
from pipeline.common.functional import partition
from pipeline.common.config import CONFIG

pp = pprint.PrettyPrinter(indent=4)

project_id = CONFIG['project_id']

server = read_config(project_id, 'snipeit')['server']
token = read_config(project_id, 'snipeit')['token']
splunk_token = read_config(project_id, 'snipeit')['splunk']

BATCH_SIZE = 2000


def _get_users(client):
    uri = '/api/v1/users'
    params = {'limit': DEFAULT_RESULT_LIMIT}

    return client._make_paginated_get_request(uri, params=params)


def _get_assets(client):
    uri = '/api/v1/hardware'
    params = {'limit': DEFAULT_RESULT_LIMIT}

    return client._make_paginated_get_request(uri, params=params)


def _extras_into_event(sourcetype, timestamp, batch_id, value):
    # adds HEC event metadata to be set in splunk.py plus batch id to identify run id in splunk
    # the companion function to this is publish and into_event in splunk.py
    # if you want more metadata fields for HEC eg host, you need to add it both here and in publish
    logger.debug(
        f'trying to fix up: sourcetype: {sourcetype} batch_id: {batch_id} timestamp: {timestamp}, value: {value}'
    )
    value['sourcetype_override'] = sourcetype
    value['time'] = timestamp
    value['batchid'] = batch_id

    return value


def _fetch():
    snipeit_client = SnipeIT(server, token)

    users = _get_users(snipeit_client)
    assets = _get_assets(snipeit_client)

    timestamp = round(datetime.now(timezone.utc).timestamp(), 0)
    batch_id = uuid.uuid4().hex

    users_m = map(
        partial(_extras_into_event, 'snipeit:users', timestamp, batch_id),
        users)

    assets_m = map(
        partial(_extras_into_event, 'snipeit:assets', timestamp, batch_id),
        assets)

    return flatten([users_m, assets_m])


def _process(records):
    total_event_count = len(records)

    logger.info(
        f'Total of {total_event_count} fetched SnipeIT, about to publish to Splunk'
    )

    batches = partition(list(records), BATCH_SIZE)
    http = retryable()
    batch_count = 1
    sum_event_count = 0
    for batch in batches:
        publish(http,
                batch,
                splunk_token,
                time_field="time",
                sourcetype_field='sourcetype_override')
        sum_event_count += len(batch)
        batch_count += 1

    logger.info(
        f'Published a total of {total_event_count} from SnipeIT into Splunk')


def _publish_snipeit():
    _process(list(_fetch()))


@click.group()
def cli():
    pass


@cli.command()
def fetch():
    pp.pprint(list(_fetch()))


@cli.command()
def process():
    _publish_snipeit()


if __name__ == '__main__':
    cli()
