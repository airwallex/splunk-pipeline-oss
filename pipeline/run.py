#!/usr/bin/env python3
"""Creating a new dataflow from a GCP filter Splunk HEC endpoint"""

import os
import pprint
import click
from google.cloud import resource_manager
from google.cloud import pubsub
from googleapiclient.discovery import build
import googleapiclient.discovery
from google.cloud import logging_v2
from google.cloud.logging_v2.services import config_service_v2
import base64
from pipeline.common.splunk import SPLUNK_HEC_URL

REGION = 'us-central1'
ZONE = 'us-central1-f'

pp = pprint.PrettyPrinter(indent=4)

from pipeline.common.config import CONFIG


@click.group()
def cli():
    pass


@cli.command()
@click.option("--project", required=True)
@click.option("--region", required=True)
def list_flows(project, region):
    df_service = build('dataflow', 'v1b3')
    result = df_service.projects().locations().jobs().list(
        projectId=project, location=region).execute()
    pp.pprint(
        list(
            filter(lambda job: job['currentState'] == 'JOB_STATE_RUNNING',
                   result['jobs'])))


@cli.command()
@click.option("--project", required=True)
@click.option("--jobid", required=True)
@click.option("--region", required=True)
def get_flow(project, jobid, region):
    df_service = build('dataflow', 'v1b3')
    pp.pprint(df_service.projects().locations().jobs().get(
        projectId=project, jobId=jobid, location=region,
        view="JOB_VIEW_ALL").execute())


def read_token(token):
    with open(f'secrets/{token}/splunk-hec-token-encrypted', 'rb') as file:
        data = file.read()
        return base64.b64encode(data).decode()


company = CONFIG['company']


@cli.command()
@click.option("--project", required=True)
@click.option("--name", required=True)
@click.option("--token", required=True)
@click.option("--release", required=True)
@click.option("--transform", required=True)
@click.option("--function", required=True)
def template(project, name, token, release, transform, function):
    """See https://cloud.google.com/dataflow/docs/reference/rest/v1b3/projects.locations.templates/create"""
    dataflow = build('dataflow', 'v1b3')
    result = dataflow.projects().templates().launch(
        projectId=project,
        body = {
          "environment": {
            "zone": ZONE,
            'machineType': 'n1-standard-4',
            'maxWorkers': 16,
            'network': 'export-network',
            'subnetwork': f'regions/{REGION}/subnetworks/export-network-us-central',
            "ipConfiguration":'WORKER_IP_PRIVATE'
          },
          "parameters": {
              'inputSubscription': f'projects/{project}/subscriptions/{name}-sub',\
              'outputDeadletterTopic' : f'projects/{project}/topics/{name}-dl-sub',\
              'tokenKMSEncryptionKey': f'projects/{project}/locations/{REGION}/keyRings/export-keys/cryptoKeys/hec-token-key',\
              'url': f'https://http-inputs.{company}.splunkcloud.com',
              'token': read_token(token),
              'batchCount': '5000',
              'parallelism': '64',
              'javascriptTextTransformGcsPath' : transform,
              'javascriptTextTransformFunctionName': function
          },
          "jobName": name
        },
        gcsPath = f'gs://dataflow-templates/{release}/Cloud_PubSub_to_Splunk'
      ).execute()


if __name__ == '__main__':
    cli()
