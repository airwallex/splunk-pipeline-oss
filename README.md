# Intro

This project enables automated audit log fetching from multiple sources into Splunk indexes, using two main mechanisms:


* Custom log [fetchers](DOCS/fetchers.md) which are [deployed](DOCS/deployment.md) as a single GCP function and triggered by a scheduler (supporting Jira, Confluence, Google worksspace etc..), check also how to [run](DOCS/development.md) it locally.

* Deployment automation for Dataflow jobs as describe in this [post](https://cloud.google.com/architecture/deploying-production-ready-log-exports-to-splunk-using-dataflow) check [dataflow](DOCS/dataflow.md)
 for more details.

This project is actively used and maintained by Airwallex Infosec team <img src="./img/infosec.svg" width="20">

# Copyright and license

Copyright [2022] [Airwallex (Hong Kong) Limited]

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.
