#!/usr/bin/env python3

import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from secops_common.logsetup import logger
from secops_common.misc import serialize
from functools import partial
import json
import click

from requests.packages.urllib3.exceptions import InsecureRequestWarning
# Fixing warning message see https://stackoverflow.com/questions/27981545/suppress-insecurerequestwarning-unverified-https-request-is-being-made-in-python
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from pipeline.common.config import CONFIG

company = CONFIG['company']

SPLUNK_HEC_URL = f'https://http-inputs.{company}.splunkcloud.com/services/collector/event'

APP = 'INFOSEC-app'

SPLUNK_REST_URL = f'https://{company}.splunkcloud.com:8089/servicesNS/nobody/{APP}/'


def logging_hook(response, *args, **kwargs):
    if (response.status_code != 200):
        logger.info(f'{response.status_code}')


def retryable():
    http = requests.Session()
    http.hooks["response"] = [logging_hook]
    retries = Retry(total=5,
                    backoff_factor=0.1,
                    status_forcelist=[500, 502, 503, 504],
                    method_whitelist=['POST'])

    http.mount('https://', HTTPAdapter(max_retries=retries))
    return http


def get_clear_sourcetype(record, sourcetype_field):
    #grabs the sourcetype value and unsets it in the record to be then set in event metadata
    if (sourcetype_field):
        sourcetype_value = record[sourcetype_field]
        del record[sourcetype_field]
        return sourcetype_value
    else:
        return None


def into_event(time_field, sourcetype_field, record):
    # https://docs.splunk.com/Documentation/Splunk/9.0.1/Data/HECExamples
    # wraps the records into an event and adds event metadata for time and sourcetype
    sourcetype_value = get_clear_sourcetype(record, sourcetype_field)
    event = {'event': record}
    if (time_field != None):
        event['time'] = record[time_field]
    if (sourcetype_field != None):
        event['sourcetype'] = sourcetype_value
    return json.dumps(event)


def publish(http, events, token, time_field=None, sourcetype_field=None):
    authHeader = {'Authorization': f'Splunk {token}'}
    payload = ''.join(
        list(map(partial(into_event, time_field, sourcetype_field), events)))
    logger.debug(f'payload consists of {len(events)} events')

    r = http.post(SPLUNK_HEC_URL,
                  headers=authHeader,
                  data=str.encode(payload),
                  verify=False)

    if (r.status_code != 200):
        raise Exception(
            f'failed to persist event to Splunk HEC endpoint {r.status_code}')


# See https://dev.splunk.com/enterprise/docs/developapps/manageknowledge/kvstore/usetherestapitomanagekv/


def insert_batch_kv(http, name, data, token, timeout=1):
    path = SPLUNK_REST_URL + f'storage/collections/data/{name}/batch_save'
    headers = {'Authorization': f'Bearer {token}'}
    r = http.post(path, headers=headers, json=data, verify=False, timeout=2)

    if (r.status_code != 200):
        raise Exception(
            f'failed to insert data into collection against Splunk Rest endpoint {path} {r.status_code} {r.content}'
        )


def empty_collection(http, name, token):
    path = SPLUNK_REST_URL + f'storage/collections/data/{name}'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    r = http.delete(path, headers=headers, verify=False)

    if (r.status_code != 200):
        raise Exception(
            f'failed to delete data from collection using Splunk Rest endpoint {path} {r.status_code} {r.content}'
        )
