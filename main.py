#!/usr/bin/env python3
"""Splunk Audit logs collection function """

# Payload deserialization
import json
import base64

# Routing
from enum import Enum, auto

# Main server listener
# from dataflow.common.listener import listen

# Logging
from secops_common.logsetup import logger, enable_logfile

# Confluence
from pipeline.confluence import _publish_confluence_logs

# Jira
from pipeline.jira import _publish_jira_logs

# Spreadsheet
from pipeline.spreadsheet import _publish_spreadsheet

# Google workspace
from pipeline.workspaces import _publish_workspace_logs

# Gmail
from pipeline.gmail import _publish_gmail_logs

# Atlassian admin console
from pipeline.atlassian_org import _publish_atlassian_logs

# Lastpass
from pipeline.lastpass import _publish_lastpass_logs

# Maxmind
from pipeline.maxmind import _publish_and_download_maxmind

# Bamboo
from pipeline.bamboo import _publish_and_download_bamboo


class Service(Enum):
    confluence = auto()
    spreadsheet = auto()
    jira = auto()
    atlassian = auto()
    lastpass = auto()
    google_workspace = auto()
    gmail = auto()
    maxmind = auto()
    bamboo = auto()


def into_service(string):
    return Service[string]


def trigger_processing(payload):
    service = into_service(payload['service'])
    if service == Service.confluence:
        _publish_confluence_logs(-1, 'minutes')
    elif service == Service.jira:
        _publish_jira_logs(-1, 'minutes')
    elif service == Service.spreadsheet:
        _publish_spreadsheet(payload['id'], payload['range'])
    elif service == Service.atlassian:
        _publish_atlassian_logs(-1, 'minutes')
    elif service == Service.lastpass:
        _publish_lastpass_logs(-1, 'minutes')
    elif service == Service.google_workspace:
        _publish_workspace_logs(-1, 'minutes', payload['type'])
    elif service == Service.gmail:
        _publish_gmail_logs(-1, 'minutes')
    elif service == Service.maxmind:
        _publish_and_download_maxmind()
    elif service == Service.bamboo:
        _publish_and_download_bamboo()


""" Processing messages in the cloud function:
      The payload has the following structure {"service":"aliyun", "asset":"disks", "dest":"biquery"} """


def process_message(event, context):
    logger.debug('Starting to process a Splunk pipeline data collection event')

    if 'data' in event:
        payload = json.loads(base64.b64decode(event['data']).decode('utf-8'))
        trigger_processing(payload)
    else:
        logger.error('no data found in message payload', extra=payload)
        raise Exception('no data found in message payload')


""" Processing messages in the server:
      The payload has the following structure {"service":"confluence"} """


def process_server_message(message):
    logger.debug('Starting to process a dataflow data collection messages')
    payload = json.loads(message.data)
    trigger_processing(payload)
    message.ack()


if __name__ == "__main__":
    enable_logfile('splunk.log')
    listen('splunk-server-listenr', process_server_message)
