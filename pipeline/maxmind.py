#!/usr/bin/env python3
"""Maxmind ASN data into Splunk K/V store"""

import urllib.request

# UI
import pprint
import click

import zipfile
import glob
import csv

from secops_common.logsetup import logger
from secops_common.secrets import read_config
from pipeline.common.functional import partition

# Splunk KV
from pipeline.common.splunk import insert_batch_kv, empty_collection, retryable

import hashlib

from pipeline.common.config import CONFIG

project_id = CONFIG['project_id']

license_key = read_config(project_id, 'maxmind')['license']

splunk_token = read_config(project_id, 'splunk_api')['token']

BASE_URL = 'https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-ASN-CSV'
EXT = 'zip'

pp = pprint.PrettyPrinter(indent=4)


def sha256sum(filename):
    h = hashlib.sha256()
    b = bytearray(128 * 1024)
    mv = memoryview(b)
    with open(filename, 'rb', buffering=0) as f:
        for n in iter(lambda: f.readinto(mv), 0):
            h.update(mv[:n])
    return h.hexdigest()


def extract_maxmind():
    with zipfile.ZipFile(f'/tmp/maxmind.{EXT}', 'r') as zip_ref:
        zip_ref.extractall('/tmp/maxmind/')


def download_maxnmind():
    logger.info(f'Downloading Maxmind file')
    urllib.request.urlretrieve(
        f'{BASE_URL}&license_key={license_key}&suffix={EXT}',
        f'/tmp/maxmind.{EXT}')
    urllib.request.urlretrieve(
        f'{BASE_URL}&license_key={license_key}&suffix={EXT}.sha256',
        f'/tmp/maxmind.{EXT}.sha256sum')


def validate_maxmind_archive():
    logger.info(f'Validating Maxmind file')
    local = sha256sum(f'/tmp/maxmind.{EXT}')
    remote = open(f'/tmp/maxmind.{EXT}.sha256sum', 'r').read().split()[0]
    return local == remote


def process():
    http = retryable()
    logger.info('Emptying geoip_asn_coll')
    empty_collection(http, 'geoip_asn_coll', splunk_token)
    for name in glob.glob('/tmp/maxmind/**/*.csv'):
        input_file = csv.DictReader(open(name))
        batches = partition(list(input_file), 5000)
        logger.info(f'Populating geoip_asn_coll using {name}')
        for batch in batches:
            insert_batch_kv(http,
                            'geoip_asn_coll',
                            batch,
                            splunk_token,
                            timeout=2)


def _publish_and_download_maxmind():
    download_maxnmind()
    extract_maxmind()
    if (not validate_maxmind_archive()):
        raise Exception(
            f'Failed to validate downloaded Maxmind {EXT} file against its checksum!'
        )
    else:
        logger.info(f'Maxmind {EXT} downloaded and validated')
    process()
    logger.info('Latest Maxmind ASN has been updated')


@click.group()
def cli():
    pass


@cli.command()
def download():
    _publish_and_download_maxmind()


if __name__ == '__main__':
    cli()
