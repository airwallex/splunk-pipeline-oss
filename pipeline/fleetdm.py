from secops_common.logsetup import logger
from secops_common.bigquery import delete_table_and_view
from secops_common.secrets import read_config

from pipeline.common.config import CONFIG
from pipeline.common.functional import partition
from pipeline.common.time import unix_time_millis
from pipeline.common.splunk import publish, retryable
from pipeline.common.fetch import last_from_id, mark_last_fetch_id

from datetime import datetime, timezone
from functools import partial
import requests
import uuid

# UI
import pprint
import click

pp = pprint.PrettyPrinter(indent=4)

project_id = CONFIG['project_id']
base = CONFIG['fleetdm_base']

token = read_config(project_id, 'fleetdm')['token']
splunk_token = read_config(project_id, 'fleetdm')['splunk']


@click.group()
def cli():
    pass


headers = {"Authorization": f"Bearer {token}"}
endpoint = '/api/v1/fleet/activities?page={index}&per_page=100&order_key=id&order_direction=desc'


def get_result(response):
    if (response == None):
        return None
    elif (response.status_code != 200):
        return None
    else:
        return response.json()['activities']


# Collect logs with IDs bigger than specified ID
def from_id(result, id):
    recent_result = []
    curr_id = result[0]['id']

    for result in result:
        if result['id'] > id:
            recent_result.append(result)
        elif result['id'] == id:
            break

        curr_id -= 1

    return (curr_id, recent_result)


# Add Splunk event metadata
def _extras_into_event(sourcetype, batch_id, value):
    timestamp = unix_time_millis(
        datetime.strptime(value['created_at'],
                          '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc))

    value['sourcetype_override'] = sourcetype
    value['timestamp'] = timestamp
    value['batch_id'] = batch_id

    return value


def _get_logs(id):
    prev_id = int(id)

    logger.debug(
        f'Getting logs from FleetDM from ID {prev_id} (non-inclusive)')
    results = []
    index = 0

    url = base + endpoint.format(index=index)
    http = retryable()
    response = http.get(url, headers=headers)

    result = get_result(response)
    latest_id = result[0]['id']

    if (result != None):
        curr_id, recent_result = from_id(result, prev_id)
        results.extend(recent_result)

    # Pagination
    while (response.json()['meta']['has_next_results'] != False
           and curr_id > prev_id):
        index += 1
        url = base + endpoint.format(index=index)
        response = http.get(url, headers=headers)

        result = get_result(response)
        if (result != None):
            curr_id, recent_result = from_id(result, prev_id)
            results.extend(recent_result)

    logger.debug(f'Total of {len(results)} logs fetched in _get_logs FleetDM')

    return results, latest_id


def _publish_fleetdm_logs(id):
    if (int(id) >= 0):
        logger.info(f'Publishing FleetDM logs from ID {id} (non-inclusive)')

        (logs, latest_id) = _get_logs(id)

    else:
        logger.info(f'Publishing FleetDM logs from last fetch ID')

        (logs, latest_id), prev_id = last_from_id(_get_logs, 'fleet_log_fetch')

    logger.info(f'Total of {len(logs)} fetched from FleetDM')

    # Publish to Splunk
    batch_id = uuid.uuid4().hex
    events = list(
        map(partial(_extras_into_event, 'fleetdm_activity_logs', batch_id),
            logs))
    batches = partition(events, 50)
    http = retryable()
    for batch in batches:
        publish(http,
                batch,
                splunk_token,
                time_field='timestamp',
                sourcetype_field='sourcetype_override')

    if (len(logs) > 0):
        logger.info(f'Total of {len(logs)} persisted into Splunk from FleetDM')

    # Store last fetched ID in bigquery
    if (int(id) < 0):
        mark_last_fetch_id(latest_id, len(logs), 'fleet_log_fetch')


@cli.command()
@click.option("--id", required=True)
def publish_logs(id):
    _publish_fleetdm_logs(id)


@cli.command()
def purge():
    delete_table_and_view('fleet_log_fetch')


@cli.command()
@click.option("--id", required=True)
def get_logs(id):
    if (int(id) >= 0):
        (logs, _) = _get_logs(id)
    else:
        (logs, latest_id), prev_id = last_from_id(_get_logs, 'fleet_log_fetch')

    logger.info(f'Total of {len(logs)} logs fetched from FleetDM')


if __name__ == '__main__':
    cli()
