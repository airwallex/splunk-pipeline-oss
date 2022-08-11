#!/usr/bin/env python3
"""Creating a new dataflow from a GCP filter Splunk HEC endpoint"""

import json
import os
import pprint
import click
from google.cloud import resource_manager
from google.cloud import pubsub
from googleapiclient.discovery import build
import googleapiclient.discovery
from google.cloud import logging_v2
from google.cloud.logging_v2.services import config_service_v2
from pipeline.common.config import CONFIG

pp = pprint.PrettyPrinter(indent=4)

ORG_ID = CONFIG['gcp_org_id']
PARENT = f'organizations/{ORG_ID}'


def set_policy(topic, project, account):
    """See https://github.com/googleapis/python-pubsub/blob/master/samples/snippets/iam.py"""
    publisher = pubsub.PublisherClient()
    topic_name = f'projects/{project}/topics/{topic}'
    policy = publisher.get_iam_policy(request={"resource": topic_name})
    policy.bindings.add(role='roles/pubsub.publisher', members=[account])
    print(publisher.set_iam_policy({'resource': topic_name, 'policy': policy}))


def create_topic(topic, project):
    publisher = pubsub.PublisherClient()
    topic_name = f'projects/{project}/topics/{topic}'
    publisher.create_topic(name=topic_name)
    print(f'Created topic {topic}')


def delete_topic(topic, project):
    publisher = pubsub.PublisherClient()
    topic_name = f'projects/{project}/topics/{topic}'
    publisher.delete_topic(request={'topic': topic_name})
    print(f'Deleted topic {topic}')


def create_subsription(name, topic, project):
    publisher = pubsub.PublisherClient()
    topic_path = publisher.topic_path(project, topic)

    with pubsub.SubscriberClient() as subscriber:
        sub_path = subscriber.subscription_path(project, name)
        subscriber.create_subscription(request={
            "name": sub_path,
            "topic": topic_path
        })

    print(f'Created subscription {name}')


def delete_subscription(name, project):
    sub_path = f'projects/{project}/subscriptions/{name}'
    with pubsub.SubscriberClient() as subscriber:
        subscriber.delete_subscription(request={"subscription": sub_path})

    print(f'Deleted subscription {name}')


def get_sink(name):
    client = config_service_v2.ConfigServiceV2Client()
    return client.get_sink(sink_name=f'organizations/{ORG_ID}/sinks/{name}')


def create_sink(name, topic, project, _filter, exclusions):
    logging_client = build('logging', 'v2')
    destination = f'pubsub.googleapis.com/projects/{project}/topics/{topic}'
    sink = logging_client.organizations().sinks().create(parent=PARENT,
                                                         body={
                                                             'name':
                                                             name,
                                                             'filter':
                                                             _filter,
                                                             'exclusions':
                                                             exclusions,
                                                             'destination':
                                                             destination,
                                                             'includeChildren':
                                                             True
                                                         }).execute()
    print(f'Created sink {name}')


def delete_sink(name, project):
    logging_client = logging_v2.Client()
    sink = logging_v2.Sink(name, parent=PARENT)
    sink.delete(client=logging_client)
    print(f'Deleted sink {sink.name}')


@click.group()
def cli():
    pass


def load_exclusions(ex):
    with open(ex) as json_file:
        exs = json.load(json_file)
        return list(
            map(lambda item: {
                'name': item[0],
                'filter': item[1]
            }, exs.items()))


@cli.command()
@click.option("--name", required=True)
@click.option("--project", required=True)
@click.option("--filter", required=True)
@click.option("--exclusions", required=False)
def create(name, project, filter, exclusions=None):
    if exclusions != None:
        exs = load_exclusions(exclusions)
    else:
        exs = []
    create_topic(name, project)
    create_subsription(f'{name}-sub', name, project)
    create_topic(f'{name}-dl', project)
    create_subsription(f'{name}-dl-sub', name, project)
    create_sink(f'{name}-sink', name, project, filter, exs)
    sink = get_sink(f'{name}-sink')
    set_policy(name, project, sink.writer_identity)


@cli.command()
@click.option("--name", required=True)
@click.option("--project", required=True)
def destroy(name, project):
    delete_subscription(f'{name}-dl-sub', project)
    delete_subscription(f'{name}-sub', project)
    delete_topic(name, project)
    delete_topic(f'{name}-dl', project)
    delete_sink(f'{name}-sink', project)


@cli.command()
def list_sinks():
    logging_client = logging_v2.Client()
    sinks = list(
        map(lambda sink: f'{sink.name} | {sink.destination} | {sink.parent}',
            (logging_client.list_sinks(parent=PARENT))))
    for sink in sinks:
        print(sink)


@cli.command()
@click.option("--name", required=True)
def desc_sink(name):
    logging_client = build('logging', 'v2')
    pp.pprint(logging_client.organizations().sinks().get(
        sinkName=f'organizations/{ORG_ID}/sinks/{name}').execute())


if __name__ == '__main__':
    cli()
