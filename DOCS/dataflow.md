# Intro

In order to stream Stackdriver logs from GCP into Splunk we use GCP [dataflow](https://cloud.google.com/dataflow) job implemented at this [repository](https://github.com/GoogleCloudPlatform/DataflowTemplates/blob/master/src/main/java/com/google/cloud/teleport/templates/PubSubToSplunk.java), see this [guide](https://cloud.google.com/architecture/deploying-production-ready-log-exports-to-splunk-using-dataflow) for the official documentation (see [caveats](DOCS/caveats.md) for additional issues we have resolved).


#  Usage

Create an HEC endpoint in Splunk get its token and place it under (name should be the same in all the steps that follow):

```bash
secrets/<name>/splunk-hec-token-plaintext
```

Encrypt the token using:

```bash
export REGION_ID=us-central1
gcloud kms encrypt \
        --key=hec-token-key \
        --keyring=export-keys \
        --location=$REGION_ID \
        --plaintext-file=./splunk-hec-token-plaintext \
        --ciphertext-file=./splunk-hec-token-encrypted
```

In order to create a new dataflow pipeline from a GCP logs filter (see [filters](filters.md) that we use in our dataflow jobs):

```bash
./pipeline/management.py create --name=<name> --project=[your project] --filter='<stackdrive log filter>'
```

Now we can lauch our dataflow pipeline:

```bash

# Standard udf template
./pipeline/run.py template --project='[your project]' --name=<name> --token=<name> --transform='gs://splk-public/js/dataflow_udf_messages_replay.js' --function='process' --release=latest
# Custom udf template
./pipeline/run.py template --project='[your project]' --name=<name> --token=<name> --transform='gs://[your-bucket]/[your udf].js' --function='[fn name]' --release=latest
# Specificy the specific version of the dataflow release we use
./pipeline/run.py template --project='[your project]' --name=<name> --token=<name> --release=2021-07-26-00_RC00
```

In order view the available job releases:

```bash
gsutil ls "gs://dataflow-templates/2021-*" | grep Splunk$
```
