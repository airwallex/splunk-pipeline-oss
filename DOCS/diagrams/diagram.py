from diagrams import Cluster, Diagram
from diagrams.gcp.analytics import BigQuery, PubSub
from diagrams.gcp.compute import Functions
from diagrams.gcp.devtools import Scheduler
from diagrams.generic.storage import Storage


with Diagram("Splunk Pipeline", show=False):
    pubsub = PubSub("pubsub")

    with Cluster("Scheduler"):
        [Scheduler('Jira'),
         Scheduler('Google drive'),
         Scheduler('Lastpass')] >> pubsub

    function = Functions('Pipeline function')
    state = BigQuery('Fetch state')
    pubsub >> function
    function >> state
    function >> Storage('splunk')

