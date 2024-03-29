We schedule each job that triggers a message to the function:

```bash
$ ./secops_common/bin/schedule splunk-pipeline-confluence "*/5 * * * *" '{"service":"confluence"}'

# Maxmind updates ASN data once a week https://support.maxmind.com/hc/en-us/articles/4408216129947-Download-and-Update-Databases
$ ./secops_common/bin/schedule splunk-pipeline-maxmind "0 0 * * 5" '{"service":"maxmind"}'

$ ./secops_common/bin/schedule splunk-pipeline-bamboo-kv "0 */4 * * *" '{"service":"bamboo_kv"}'

$ ./secops_common/bin/schedule splunk-pipeline-bamboo-hec "*/10 * * * *" '{"service":"bamboo_hec"}'

$ ./secops_common/bin/schedule splunk-pipeline-jira "*/5 * * * *" '{"service":"jira"}'

$ ./secops_common/bin/schedule splunk-pipeline-spreadsheet "*/5 * * * *" '{"service":"spreadsheet", "id":"..", "range":"..."}'

$ ./secops_common/bin/schedule splunk-pipleline-ms_graph_inventory "*/20 * * * *" '{"service":"ms_graph_inventory"}'

$ ./secops_common/bin/schedule splunk-pipleline-snipeit "*/60 * * * *" '{"service":"snipeit"}'

$ ./secops_common/bin/schedule splunk-pipleline-fleetdm "*/10 * * * *" '{"service":"fleetdm"}'

# workspace
$ ./secops_common/bin/schedule splunk-pipeline-google_workspace_login "*/5 * * * *" '{"service":"workspace", "type":"login"}'

$ ./secops_common/bin/schedule splunk-pipeline-google_workspace_admin "*/5 * * * *" '{"service":"workspace", "type":"admin"}'

$ ./secops_common/bin/schedule splunk-pipeline-google_workspace_drive "*/5 * * * *" '{"service":"workspace", "type":"drive"}'

$ ./secops_common/bin/schedule splunk-pipeline-gmail "*/5 * * * *" '{"service":"gmail"}'

# Aliyun
$ ./secops_common/bin/schedule splunk-pipeline-aliyun-sas-alerts_{account}" */5 * * * *" '{"service":"aliyun_sas", "type":"alerts", "account":"..."}'

$ ./secops_common/bin/schedule splunk-pipeline-aliyun-sas-leaks_{account} "*/5 * * * *" '{"service":"aliyun_sas", "type":"leaks", "account" : "..."}'

$ ./secops_common/bin/schedule splunk-pipeline-aliyun-sas-exposed_{account} "0 * * * *" '{"service":"aliyun_sas", "type":"exposed", "account":"..."}'

$ ./secops_common/bin/schedule splunk-pipeline-aliyun-sas-risk_{account} "0 * * * *" '{"service":"aliyun_sas", "type":"risks", "account":"..."}'

```


