#!/usr/bin/env python3

# collector for inventory of azure devices, users, and intune managed devices via graph api
import json
from stat import FILE_ATTRIBUTE_ENCRYPTED

# azure identity is stable
from azure.identity import ClientSecretCredential

# beta roadmap here: https://github.com/microsoftgraph/msgraph-sdk-design
from msgraph.core import APIVersion, GraphClient, NationalClouds
from pipeline.common.splunk import publish, retryable
from pipeline.common.config import CONFIG
from pipeline.common.functional import partition
from secops_common.secrets import read_config
from functools import reduce, partial

from secops_common.logsetup import logger
from secops_common.functional import merge, compose2, flatten

from datetime import datetime, timezone

import uuid
# UI
import pprint
import click
import sys

pp = pprint.PrettyPrinter(indent=4)

project_id = CONFIG['project_id']

auth_map = read_config(project_id, 'ms_graph_api_aad_intune')
splunk_token = auth_map['splunk']
Write_File = False
scope = 'https://graph.microsoft.com/.default'

BATCH_SIZE = 5000


def init_clients_creds():
    logger.debug("setting v1 graph client")
    tenant_id = auth_map["tenant_id"]
    client_id = auth_map["client_id"]
    app_secret = auth_map["app_secret"]
    secret_id = auth_map[
        "secret_id"]  #can facilitate tracking auth issues by id in the app

    logger.debug(
        f'setting graph api client: {tenant_id}, clientid(app_id): {tenant_id}, secret id: {secret_id}'
    )
    creds = ClientSecretCredential(tenant_id=tenant_id,
                                   client_id=client_id,
                                   client_secret=app_secret)

    return creds


def graph_generator_f(graph_client, endpoint=None, max_page=3):
    # ref based on https://github.com/microsoftgraph/python-sample-pagination pattern
    # endpoint is either the original url or nextLink page ref
    page_num = 1

    cumulative_item_count = 0
    logger.info(f'about to start collecting from: {endpoint}')
    logger.debug(f'max_page is {max_page}')

    while endpoint and (max_page == 0 or page_num <= max_page):
        logger.debug(
            f'Retrieving page number: {page_num} from url: {endpoint}')
        response_raw = graph_client.get(endpoint).json()
        if "value" in response_raw:
            logger.debug(f'response_raw: {str(response_raw)[1:500]}')
        else:
            logger.error(
                f'unable to find a valid graph api response: {str(response_raw)[1:500]}'
            )

        page_records_batch = response_raw["value"]
        cumulative_item_count += len(page_records_batch)
        logger.debug(
            f'collected items: {len(page_records_batch)}, cumulative count {cumulative_item_count}'
        )
        yield from page_records_batch
        endpoint = response_raw[
            "@odata.nextLink"] if "@odata.nextLink" in response_raw else None
        logger.debug(f'next page url is {endpoint}')
        page_num += 1


def make_base_url(endpoint, page_size=500, extra_args=None):
    page_size_str = f'$top={str(page_size)}' if page_size > 0 else ""
    extra_args_str = f'{extra_args}' if extra_args else ""
    first_args_separator = "" if (page_size_str == ""
                                  and extra_args_str == "") else "?"
    next_arg_separator = "&" if (page_size_str != ""
                                 and extra_args_str != "") else ""
    url = f'{endpoint}{first_args_separator}{page_size_str}{next_arg_separator}{extra_args_str}'
    return url


def query_items_all(graph_client,
                    base_url,
                    max_page=3,
                    page_size=500,
                    extra_args=None):
    # ref: https://docs.microsoft.com/en-us/graph/query-parameters
    api_result_list = []
    url = make_base_url(base_url, page_size, extra_args)
    paging_is_enabled = page_size > 0

    logger.debug(f'about to fetch from api endpoint: {base_url}')
    logger.debug(
        f'paging_enabled: {paging_is_enabled}, max_page: {max_page}, page_size {page_size}'
    )

    graph_results = graph_generator_f(graph_client=graph_client,
                                      endpoint=url,
                                      max_page=max_page)

    for gen_values in graph_results:
        api_result_list.append(gen_values)
    return api_result_list


def get_az_devices(graph_client):
    api_ret_list = query_items_all(graph_client,
                                   base_url="/devices",
                                   max_page=0,
                                   page_size=500)
    logger.debug(f'collected device objects {len(api_ret_list)}')
    return api_ret_list


def get_az_users(graph_client):
    api_ret_list = query_items_all(graph_client,
                                   base_url="/users",
                                   max_page=0,
                                   page_size=500)
    logger.debug(f'collected user objects {len(api_ret_list)}')
    return api_ret_list


def get_az_groups(graph_client, expand=False):
    # IDEA: from a splunk perspective splitting members as a separate collection
    # with group ID and NAME + member expanded is easier to work with
    api_ret_list = query_items_all(graph_client,
                                   base_url="/groups",
                                   max_page=0,
                                   page_size=500,
                                   extra_args="$expand=members")
    logger.debug(f'collected group objects {len(api_ret_list)}')
    return api_ret_list


def get_intune_managed_devices(graph_client):
    # Note: requires an active Intune license for the tenant.
    api_ret_list = query_items_all(graph_client,
                                   base_url="/deviceManagement/managedDevices",
                                   max_page=0,
                                   page_size=500)
    logger.debug(f'collected managed device objects {len(api_ret_list)}')
    return api_ret_list


def write_to_json_file(api_ret_object_list, out_filename, Format=False):

    l_indent = 0
    if (Format):
        l_indent = 4

    with open(out_filename, 'w', encoding='utf-8') as outfile:
        json.dump(api_ret_object_list, outfile, indent=l_indent)


def extras_into_event(sourcetype, timestamp, batch_id, value):
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
    creds = init_clients_creds()  #
    graph_client_beta = GraphClient(credential=creds,
                                    api_version=APIVersion.beta,
                                    NationalClouds=NationalClouds.Global,
                                    max_retries=3,
                                    retry_backoff_factor=0.5)

    # for when you need endpoints that are only in beta eg intune auditEvents (log  not inventory though)
    graph_client_v1 = GraphClient(credential=creds,
                                  api_version=APIVersion.v1,
                                  NationalClouds=NationalClouds.Global,
                                  max_retries=3,
                                  retry_backoff_factor=0.5)

    az_devices = get_az_devices(graph_client_v1)
    if (Write_File):
        write_to_json_file(az_devices, 'devices.json', Format=True)

    az_users = get_az_users(graph_client_v1)
    if (Write_File):
        write_to_json_file(az_users, 'users.json', Format=True)

    # as is you should define a sourcetype called "az:graph_groups"
    # and set TRUNCATE to 0 . else it will drop content for field extraction mid way through large json
    az_groups = get_az_groups(graph_client_v1, expand=True)

    if (Write_File):
        write_to_json_file(az_groups, 'groups.json', Format=True)

    intune_managed_devices = get_intune_managed_devices(graph_client_v1)

    if (Write_File):
        write_to_json_file(intune_managed_devices,
                           'intune_managed_devices.json',
                           Format=True)

    timestamp = round(datetime.now(timezone.utc).timestamp(), 0)
    batch_id = uuid.uuid4().hex
    az_devices_m = map(
        partial(extras_into_event, 'az:graph_devices', timestamp, batch_id),
        az_devices)
    az_users_m = map(
        partial(extras_into_event, 'az:graph_users', timestamp, batch_id),
        az_users)
    az_groups_m = map(
        partial(extras_into_event, 'az:graph_groups', timestamp, batch_id),
        az_groups)
    intune_managed_devices_m = map(
        partial(extras_into_event, 'intune:graph_managed_devices', timestamp,
                batch_id), intune_managed_devices)
    return flatten(
        [az_devices_m, az_users_m, az_groups_m, intune_managed_devices_m])


def _process(records):
    logger.info(
        f'Total of {len(records)} fetched from az and intune, about to publish to splunk'
    )
    batches = partition(list(records), BATCH_SIZE)
    http = retryable()
    batch_count = 1
    total_event_count = len(records)
    sum_event_count = 0
    for batch in batches:
        publish(http,
                batch,
                splunk_token,
                time_field="time",
                sourcetype_field='sourcetype_override')
        sum_event_count += len(batch)
        batch_count += 1

    logger.debug(f'published a total of {len(records)} into splunk')


def _publish_and_download_intune():
    _process(list(_fetch()))


@click.group()
def cli():
    pass


@cli.command()
def fetch():
    pp.pprint(list(_fetch()))


@cli.command()
def process():
    _publish_and_download_intune()


if __name__ == '__main__':
    cli()
