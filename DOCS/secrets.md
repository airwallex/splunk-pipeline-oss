# Intro

Secrets are managed directly on GCP secret manager, there is no need to locally store or share passwords using any other method.


# Usage

We create a secret for a given asset type (jumpcloud, aliyun etc..)
```bash
setopt histignorespace
 ./secops_common/bin/add_secret <asset> "{'token':..}"
```

**Note**: in order to prevent shell history from storing our password we use histignorespace option in ZSH, check [this](https://stackoverflow.com/questions/8473121/execute-a-command-without-keeping-it-in-history) for additional options for other shells.


The following secrets are expected to be set:

```bash
setopt histignorespace

 ./secops_common/bin/add_secret gitlab "{'token': <token>, 'splunk':<token>}"

 ./secops_common/bin/add_secret atlassian "{'token': <token>,'org_id': <org_id>, 'splunk':<token>}"

 ./secops_common/bin/add_secret slack "{'hook_url' : <url>}"

 ./secops_common/bin/add_secret jira "{'token': <token>, 'user':<email>, 'splunk':<token>}"

 ./secops_common/bin/add_secret confluence "{'token': <token>, 'user':<email>, 'splunk':<token>}"

 ./secops_common/bin/add_secret spreadsheet "{'splunk': <token>}"

 ./secops_common/bin/add_secret lastpass "{'token': <token>, 'splunk':<token>}"

 ./secops_common/bin/add_secret google_workspace_login "{'splunk':<token>}"

 ./secops_common/bin/add_secret google_workspace_admin "{'splunk':<token>}"

 ./secops_common/bin/add_secret google_workspace_drive "{'splunk':<token>}"

 ./secops_common/bin/add_secret google_workspace_calendar "{'splunk':<token>}"

 ./secops_common/bin/add_secret google_workspace_saml "{'splunk':<token>}"

 ./secops_common/bin/add_secret google_workspace_groups "{'splunk':<token>}"

 ./secops_common/bin/add_secret google_workspace_groups_enterprise "{'splunk':<token>}"

 ./secops_common/bin/add_secret google_workspace_rules "{'splunk':<token>}"

 ./secops_common/bin/add_secret google_workspace_user_accounts "{'splunk':<token>}"

 ./secops_common/bin/add_secret gmail "{'splunk':<token>}"

 ./secops_common/bin/add_secret bamboo "{'token': <token>, 'splunk':<token>}"
```


# Function service account access to Google resources

### Spreadsheet

In order to access the spreadsheet make sure to share it with the service account using its email address (on the document in the UI).


### Workspace

Google workspace uses [Domain Delegation](https://developers.google.com/admin-sdk/directory/v1/guides/delegation) in order to allow a remote service use to perform operations in the Google workspace context.

In order to enable such delegation:

1. Head on to Google admin delegation [page](https://admin.google.com/ac/owl/domainwidedelegation) and enable it (with the matching scopes) for the service account id you intend to use.

2. In the python code set the subject (which is the email of the user you are delegating with), ATM only [google.oauth2 service account API](https://google-auth.readthedocs.io/en/master/reference/google.oauth2.service_account.html) supports that (default auth doesn't seem to have that option).

Optionally (it doesn't seem to change the authorization outcome):

3. Go to the service accounts permission [page](https://console.cloud.google.com/apis/credentials?project=[your project]) and click on the matching service account and enable delegation (avilable at the bottom of the page)


# Atlassian tokens

For admin api a token can be generated at https://admin.atlassian.com/o/[your id]/admin-api page.

All other tokens (Jira, Confluence API) can be generated the [id.atlassian.com](https://id.atlassian.com/manage-profile/security/api-tokens) page.

