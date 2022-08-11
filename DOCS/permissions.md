Follow the next steps in order to set the minimal set of permissions required for the function to run:

```bash
$ gcloud iam service-accounts create splunk-pipeline-function --description "Splunk pipeline function service account" --display-name "splunk-pipeline-function"

$ gcloud iam roles create bigquery_secops_function --project [project] --title splunk-pipeline-bigquery-updater --description 'A role for update bigquery during splunk pipeline event publish function usage' --permissions='bigquery.tables.create,bigquery.tables.get,bigquery.tables.updateData' --stage=GA

$ gcloud projects add-iam-policy-binding [project] --member serviceAccount:splunk-pipeline-function@[project].iam.gserviceaccount.com --role "roles/bigquery.user"

$ gcloud projects add-iam-policy-binding [project] --member serviceAccount:splunk-pipeline-function@[project].iam.gserviceaccount.com --role "roles/bigquery.dataEditor"

$ gcloud projects add-iam-policy-binding [project] --member serviceAccount:splunk-pipeline-function@[project].iam.gserviceaccount.com --role "projects/[project]/roles/bigquery_secops_function"

$ gcloud secrets add-iam-policy-binding splunk-credentials-ini --role roles/secretmanager.secretAccessor --member serviceAccount:splunk-pipeline-function@[project].iam.gserviceaccount.com
```
