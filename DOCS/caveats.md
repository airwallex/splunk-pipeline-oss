# Intro

This sections covers the caveats and issues found in GCP [documentation](https://cloud.google.com/architecture/deploying-production-ready-log-exports-to-splunk-using-dataflow) for creating splunk forwarders using GCP dataflow (Apache Beam platform).

# Issues

 1. The following export:
```bash
 export SPLUNK_HEC_TOKEN=`cat ./splunk-hec-token-encrypted | base64`
```

Should be:

```bash
 export SPLUNK_HEC_TOKEN=`cat ./splunk-hec-token-encrypted | base64 -w 0 `
```

Not doing that results with "Illegal base64 character a" exception in the code (the base64 encoded token should be a single line).

 2. HEC url mentioned [here](https://cloud.google.com/architecture/deploying-production-ready-log-exports-to-splunk-using-dataflow#deploy_the_dataflow_pipeline), there isn't enough details on what the URL is, the url format is very specific and limited by a validation in the dataflow job source code, failure to match this exact format results with:

```java
Url format should match PROTOCOL://HOST[:PORT], where PORT is optional. Supported Protocols are http and https. eg: http://hostname:8088 org.apache.beam.sdk.util.UserCodeException.wrap(UserCodeException.java:39) com.google.cloud.teleport.splunk.AutoValue_SplunkEventWriter$DoFnInvoker.invokeSetup(Unknown Source)
```

The url is https://http-inputs.<company>.splunkcloud.com (figuring out which url took me some time and required some guessing)

 3. There is a requirement by Apache Beam (the engine that runs the dataflow) to open additional ports, not doing that results with a warning within the job logs:

```java
The network export-network doesn't have rules that open TCP ports 12345-12346 for internal connection with other VMs. Only rules with a target tag 'dataflow' or empty target tags set apply. If you don't specify such a rule, any pipeline with more than one worker that shuffles data will hang. Causes: Firewall rules associated with your network don't open TCP ports 12345-12346 for Dataflow instances. If a firewall rule opens connection in these ports, ensure target tags aren't specified, or that the rule includes the tag 'dataflow'.
```
In order to fix that you need to add some firewall rules:

```bash
gcloud compute firewall-rules create FIREWALL_RULE_NAME \
    --network export-network \
    --action allow \
    --direction DIRECTION \
    --target-tags dataflow \
    --source-tags dataflow \
    --priority 0 \
    --rules tcp:12345-12346
```

This isn't included in the guide.
