# Intro

In this section we will detail the deployment process of the function from setting up the code, adding its configuration and deployment into GCP.


## Code setup

The code is composed of three repos (one is optional):

1. This repo which contains the main fetching logic

2. secops_common which contains common reusable logic

3. internal, which is optional and is meant for you to add internal logic (see [transformation](transformation.md))

```bash
$ git clone https://github.com/airwallex/splunk-pipeline-oss
$ cd splunk-pipeline-oss
$ git clone https://github.com/airwallex/secops_common
# optionally if you have internal logic you want to include
$ git clone <internal repo> internal
```

## Configuration

The function expects two main configuration files to be present and set:

```bash
$ cat .env

function_service_account='function service account in GCP'
function_name='splunk-pipeline'
function_topic='splunk-pipeline'
main_topic='main-splunk-pipeline'
function_memory='8192MB'
connector_name='optional network connector used by the function'
```

And

```bash
$ cat pipeline.yml

dataset: "bigquery data set the function will use"
company: "your company name"
project: "GCP project the function will be running in"
project_id: "GCP project id that the function will be running in"
subject: "Used for workspace logs see pipeline/workspace.py"
lastpass_org_id: "Lastpass org id"
gcp_org_id: "GCP org id"
```

## Automated Deployment

secops_common contains the required script to deploy the function:

```bash
./secops_common/bin/deploy_function
```

The following is an example of using GCP cloudbuild to deploy the function from a CI process:

```yaml
steps:
  - name: 'gcr.io/cloud-builders/git'
    entrypoint: git
    args: ['clone' ,'https://github.com/airwallex/secops_common', 'secops_common']
  - name: 'gcr.io/cloud-builders/git'
    entrypoint: git
    args: ['clone' ,'https://github.com/airwallex/splunk-pipeline-oss', 'splunk-pipeline-oss']
  - name: 'gcr.io/cloud-builders/git'
    entrypoint: git
    args: ['clone' ,'your internal logic', 'internal']
  - name: 'gcr.io/cloud-builders/gcloud'
    entrypoint: 'bash'
    args: ['./bin/copy_pipeline.sh']
  - name: python:3.8
    entrypoint: pip
    args: ['install' ,'-q' ,'-r' ,'requirements.txt', '--user']
  - name: python:3.8
    entrypoint: python
    args: ['-m', 'yapf', '-r', 'pipeline', '-q']
  - name: 'gcr.io/cloud-builders/gcloud'
    entrypoint: 'bash'
    args: ['./secops_common/bin/deploy_function']
```

Where:

```bash
cat copy_pipeline.sh 

#!/usr/bin/env bash

/usr/bin/mv splunk-pipeline-oss/* .
rm -rf splunk-pipeline-oss
```

## Function topic and scheduling

Next we set up the topic the that will be used to [trigger](https://cloud.google.com/functions/docs/calling/pubsub) the function:

```bash
$ gcloud pubsub topics create splunk-pipeline
```

Set up the required secrets as specified in [secrets](DOCS/secrets.md) per fetcher type being used and enable the required [permissions](DOCS/permissions.md)

And trigger the function manually:

```bash
# Pulling the latest information into biquery
$ gcloud pubsub topics publish --message='{"service":"confluence"}' splunk-pipeline
$ gcloud pubsub topics publish --message='{"service":"jira"}' splunk-pipeline
$ gcloud pubsub topics publish --message='{"service":"spreadsheet", "id":"spreadsheet id", "range":"Example!A:G"}' splunk-pipeline

# Reviewing the logs
$ gcloud functions logs read splunk-pipeline
```

Follow [scheduling](DOCS/schedule.md) guide in order to trigger the function continuously.
