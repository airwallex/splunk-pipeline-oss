# Intro

In order to develop locally we need to clone 2 repos:

```bash
$ git clone https://github.com/airwallex/splunk-pipeline-oss
$ cd splunk-pipeline-oss
$ git clone https://github.com/airwallex/secops_common
```

Install the dependencies:

```bash
$ sudo apt install python3 python3-pip -y
$ pip3 install -r requirements.txt
# During development (to setup secops module)
$ pip3 install -e .
```

Make sure we have access to GCP:

```bash
$ gcloud auth list
      Credentialed Accounts
ACTIVE  ACCOUNT
*       [your gcp email]

$ gcloud auth application-default login
```

And make sure to set the [secrets](DOCS/secrets.md) before we run a simple fetch:

```bash
# No data will be written to Splunk, this is just listing the entries
./pipeline/bamboo.py fetch
```

Additional fetchers can be invoked similarly.

