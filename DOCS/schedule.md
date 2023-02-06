We schedule each job that triggers a message to the function:

```bash
$ ./secops_common/bin/schedule splunk-pipeline-confluence "*/5 * * * *" '{"service":"confluence"}'

# Maxmind updates ASN data once a week https://support.maxmind.com/hc/en-us/articles/4408216129947-Download-and-Update-Databases
$ ./secops_common/bin/schedule splunk-pipeline-maxmind "0 0 * * 5" '{"service":"maxmind"}'

$ ./secops_common/bin/schedule splunk-pipeline-bamboo "0 */4 * * *" '{"service":"bamboo"}'

$ ./secops_common/bin/schedule splunk-pipeline-jira "*/5 * * * *" '{"service":"jira"}'

$ ./secops_common/bin/schedule splunk-pipeline-spreadsheet "*/5 * * * *" '{"service":"spreadsheet", "id":"..", "range":"..."}'

$ ./secops_common/bin/schedule splunk-pipleline-ms_graph_inventory "*/20 * * * *" '{"service":"ms_graph_inventory"}'

# workspace
$ ./secops_common/bin/schedule splunk-pipeline-google_workspace_login "*/5 * * * *" '{"service":"workspace", "type":"login"}'

$ ./secops_common/bin/schedule splunk-pipeline-google_workspace_admin "*/5 * * * *" '{"service":"workspace", "type":"admin"}'

$ ./secops_common/bin/schedule splunk-pipeline-google_workspace_drive "*/5 * * * *" '{"service":"workspace", "type":"drive"}'

$ ./secops_common/bin/schedule splunk-pipeline-gmail "*/5 * * * *" '{"service":"gmail"}'

# Aliyun 
$ ./secops_common/bin/schedule splunk-pipeline-aliyun-sas-alerts_int "*/5 * * * *" '{"service":"aliyun_sas", "type":"alerts", "account":"INT"}'

$ ./secops_common/bin/schedule splunk-pipeline-aliyun-sas-alerts_cn "*/5 * * * *" '{"service":"aliyun_sas", "type":"alerts", "account":"CN"}'

$ ./secops_common/bin/schedule splunk-pipeline-aliyun-sas-leaks_int "*/5 * * * *" '{"service":"aliyun_sas", "type":"leaks", "account" : "INT"}'

$ ./secops_common/bin/schedule splunk-pipeline-aliyun-sas-leaks_cn "*/5 * * * *" '{"service":"aliyun_sas", "type":"leaks", "account": "CN"}'

$ ./secops_common/bin/schedule splunk-pipeline-aliyun-sas-exposed_int "0 * * * *" '{"service":"aliyun_sas", "type":"exposed", "account":"INT"}'

$ ./secops_common/bin/schedule splunk-pipeline-aliyun-sas-exposed_cn "0 * * * *" '{"service":"aliyun_sas", "type":"exposed", "account" : "CN"}'

```


