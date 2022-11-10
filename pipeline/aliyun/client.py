import configparser
from aliyunsdkcore.client import AcsClient
from secops_common.misc import deserialize
from secops_common.secrets import read_config
from pipeline.common.config import CONFIG
from pathlib import Path
import functools

# Fetch logic

project_id = CONFIG['project_id']

def _next(client, request, response):
    page = response['PageNumber'] + 1
    request.set_PageNumber(page)
    return deserialize(client.do_action_with_exception(request))


def fetch_with_token(client, request, fn):
    request.set_PageSize(20)
    response = deserialize(client.do_action_with_exception(request))
    result = fn(response)
    while ('NextToken' in response and response['NextToken'] != ''):
        result.extend(fn(response))
        response = _next(client, request, response)
        if (not 'NextToken' in response):
            response['NextToken'] = ''

    return result


def fetch_with_count(client, request, fn):
    request.set_PageSize(20)
    response = deserialize(client.do_action_with_exception(request))
    result = fn(response)
    total = response['PageRecordCount']
    page = response['PageNumber']

    while (response['TotalRecordCount'] > total):
        page += 1
        request.set_PageNumber(page)
        response = deserialize(client.do_action_with_exception(request))
        result.extend(fn(response))
        total += response['PageRecordCount']

    return result


def fetch_with_count_2(client, request, fn):
    request.set_PageSize(1000)
    response = deserialize(client.do_action_with_exception(request))
    result = fn(response)
    total = response['PageInfo']['PageSize']
    page = response['PageInfo']['CurrentPage']

    while (response['PageInfo']['TotalCount'] > total):
        page += 1
        request.set_CurrentPage(page)
        response = deserialize(client.do_action_with_exception(request))
        result.extend(fn(response))
        total += response['PageInfo']['PageSize']

    return result


""" Fetch all in one go (no pagination) """


def fetch_all(client, request, fn):
    response = deserialize(client.do_action_with_exception(request))
    return fn(response)


# See https://www.alibabacloud.com/help/doc-detail/40654.html for available regions
@functools.lru_cache(maxsize=None)
def initialize_client(region='cn-hongkong'):
    auth = read_config(project_id,'aliyun')
    return AcsClient(auth['access_key_id'], auth['access_key_secret'], region,
                     True, 360)
