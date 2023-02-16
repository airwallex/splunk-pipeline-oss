#!/usr/bin/env python
import json
import requests

from secops_common.logsetup import logger

DEFAULT_RESULT_LIMIT = 500


class SnipeIT:
    def __init__(self, server, token):
        if not server.startswith('https://'):
            raise Exception(f'Configured server url must be https: {server}')

        self.server = server
        self.token = token

    def _make_paginated_get_request(self, uri, params):
        results = []

        # Get first page
        requested_limit = params['limit']
        params['limit'] = DEFAULT_RESULT_LIMIT
        response = self._make_get_request(uri, params)
        collected = len(response['rows'])
        remaining = response['total'] - collected

        results.extend(response['rows'])

        # Get remaining pages
        while (remaining):
            remaining = requested_limit - collected

            params['limit'] = limit = DEFAULT_RESULT_LIMIT
            params['offset'] = collected
            response = self._make_get_request(uri, params)
            results.extend(response['rows'])

            collected += len(response['rows'])
            remaining = response['total'] - collected

        logger.info(f'Collected {len(results)} results')

        return results

    def _make_get_request(self, uri, params=None):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.token
        }

        response = requests.get(self.server + uri,
                                params=params,
                                headers=headers)
        data = json.loads(response.content)

        if 'rows' not in data:
            logger.error('Failed to obtain results from SnipeIT')

        return data
