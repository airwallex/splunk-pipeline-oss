# Intro

Fetchers implement the basic infra required in order to fetch log audit events from external systems, they use public API's to poll for new events.

All fetchers store the last fetched events dates and update them continuously, they all use the same fetching [algorithm](DOCS/fetch_algorithm.md).


# Fetcher listing

| Service |  Description |
|---------|--------------|
| [Atlassian Org](../pipeline/atlassian_org.py) | Org level audit logs from Atlassian. |
| [Bamboo](../pipeline/bamboo.py) |Bambooe employee kv store enrichment. |
| [Confluence](../pipeline/confluence.py) | Confluence audit logs. |
| [Gmail](../pipeline/gmail.py) |Fetching Gmail logs from BQ table [see](https://support.google.com/a/topic/7233311?hl=en&ref_topic=2683886). |
| [Jira](../pipeline/jira.py) | Jira audit logs. |
| [Lastpass](../pipeline/lastpass.py) | Lastpass audit logs. |
| [Maxmind](../pipeline/maxmind.py) | Maxmind ASN kv store. |
| [Spreadsheet](../pipeline/spreadsheet.py) | Publish any Google spreadsheet rows into Splunk as events. |
| [Google Workspace](../pipeline/workspace.py) | Publish Google workspace audit logs (Drive, Calendar, Login [etc..](https://support.google.com/a/answer/9725452?hl=en&ref_topic=9027054)) into Splunk. |
| [MS Intune inventory collector](../pipeline/ms_graph_inventory.py) | Publish AZ users, devices, groups and intune managed devices |
| [SnipeIT](../pipeline/snipeit/snipeit.py) | Publish SnipeIT users and assets (hardware) devices. |

## Historical import

Past events can be import by running locally (after we have set the local [development](DOCS/development.md) environment):

```bash
./pipeline/confluence.py publish-logs --num 730 --unit days
./pipeline/jira.py publish-logs --num 730 --unit days
./pipeline/atlassian_org.py publish-logs --num 730 --unit days

# Google workspace (max of 180 days)
./pipeline/workspaces.py publish-logs --num=180 --unit=days --type=login
```
