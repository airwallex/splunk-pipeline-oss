# Intro

Fetching events from external systems has a number of failure points which need to be taken into account:

1. External service can go down.

2. There are processing lags in external services, (see GCP Audit logs [lag](https://support.google.com/a/answer/7061566?hl=en) times) those effect the time from which an event has occured up to the point in which it was visible for consumers (via the API)

3. Splunk or GCP can go down.


This requires the following mitigations:

1. Out fetch logic must be persistent (to be able to recover once services are back online).

2. The fetch logic should be able to handle delays in delivery of events (not lose events) by using the fetching logic listed bellow.



# Fetching Algorithm

We define the following:

* M list of event we get from a remote system.
* D the number of minutes we sleep between each fetch.
* S the starting time stamp of the window we currently fetch events for.
* E the end time stamp of the window we currently fetch events for.
* W our fetch window within the time range of W[S,E].


Our Algorithm:

1. We run the search query every D minutes (D is our ~= Max latency from when an event was made available in the remote system).

2. If our current events list (M) is empty in the current window range W[S,E]:

   2.1. Keep window start (S) at the same value (don't move it forward), this will handle cases that we had a delay in the remote logs provider (past log events were not made available yet).

   2.2. Set window end (E) value to be the current time (moving forward in case we didn't have any events in first place).

   2.3. Sleep for D minutes and goto step 2.

3. If we did get events (M) in the current window (W):

   3.1 Write all events to Splunk.

   3.2. Set start time (S) to be: Max(M(timestamp)) + 1  (the last event timestamp we have found within the lastest M values plus one mili second).

   3.3. Set the end time (E) to be current timestamp (so next time we will get all the events that occurred after the last one we saw, we will never miss any event)

   3.4 Sleep for D minutes and goto step 2.

Assumptions:

1. The API will provide events by order (i.e. no events that happened in the past will be made available once we have progressed forward), this assumption was confirmed by GCP team (if this assumption breaks its a SLA violation by GCP).

Clarifications:

1. A good value for D is a number of minutes (5 min is a good start).

2. In 3.2 we add 1 to the latest timestamp found in M, this is done in order to make our next next search non inclusive (so we don't get back again the same last event we just saw).
