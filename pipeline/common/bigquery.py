#!/usr/bin/env python3
""" Common bigtable infra"""

from google.cloud import bigquery

from secops_common.logsetup import logger
from secops_common.functional import merge

import secops_common.bigquery

from google.api_core.exceptions import NotFound
from pipeline.common.config import CONFIG

bigquery_client = bigquery.Client()

SYNC_SCHEMA = [
    bigquery.SchemaField('start_date',
                         'TIMESTAMP',
                         mode='REQUIRED',
                         description='Fetch start date'),
    bigquery.SchemaField('end_date',
                         'TIMESTAMP',
                         mode='REQUIRED',
                         description='Fetch end date'),
    bigquery.SchemaField('success',
                         'BOOLEAN',
                         mode='REQUIRED',
                         description='If the fetch was sucessful'),
    bigquery.SchemaField('created_at',
                         'TIMESTAMP',
                         mode='REQUIRED',
                         description='Bigquery record creation time')
]

DEDUP_SCHEMA = [
    bigquery.SchemaField('id',
                         'string',
                         mode='REQUIRED',
                         description='The event/log id'),
    bigquery.SchemaField('created_at',
                         'TIMESTAMP',
                         mode='REQUIRED',
                         description='Bigquery record creation time')
]


def into_schema(products):
    return dict(
        list(
            map(lambda product:
                (f'{product}_log_fetch', SYNC_SCHEMA), products)) + list(
                    map(lambda product:
                        (f'{product}_log_dedup', DEDUP_SCHEMA), products)))


AUDITS = [
    'login', 'admin', 'drive', 'calendar', 'saml', 'groups',
    'groups_enterprise', 'rules', 'user_accounts', 'token'
]

WORKSPACE = into_schema(map(lambda product: f'workspace_{product}', AUDITS))

PRODUCTS = into_schema([
    'jira', 'confluence', 'atlassian', 'lastpass', 'gmail', 'aliyun_sas',
    'aliyun_sas_leaks'
])

SPREAD = {
    'spreadsheet_tracking': [
        bigquery.SchemaField('id',
                             'STRING',
                             mode='REQUIRED',
                             description='Spreadsheet Id (in Google drive)'),
        bigquery.SchemaField('checksum',
                             'STRING',
                             mode='REQUIRED',
                             description='Last spreadsheet checksum'),
        bigquery.SchemaField('created_at',
                             'TIMESTAMP',
                             mode='REQUIRED',
                             description='Bigquery record creation time')
    ]
}

secops_common.bigquery.schema = merge(merge(WORKSPACE, PRODUCTS), SPREAD)
secops_common.bigquery.dataset = CONFIG['dataset']
secops_common.bigquery.project = CONFIG['project']
