# Intro

This project enables automated audit log fetching from multiple sources into Splunk indexes, using two main mechanisms:


* Custom log [fetchers](DOCS/fetchers.md) which are [deployed](DOCS/deployment.md) as a single GCP function and triggered by a scheduler (supporting Jira, Confluence, Google worksspace etc..), check also how to [run](DOCS/development.md) it locally.

* Deployment automation for Dataflow jobs as describe in this [post](https://cloud.google.com/architecture/deploying-production-ready-log-exports-to-splunk-using-dataflow) check [dataflow](DOCS/dataflow.md)
 for more details.

This project is actively used and maintained by Airwallex Infosec team <img src="./img/infosec.svg" width="20">
