import time
import json
import functools
from flask import g

import requests
from sentinelhub import SentinelHubSession
from openeoerrors import Internal

from const import SentinelhubDeployments
from usage_reporting.report_usage import report_usage


class ProcessingAPIRequest:
    def __init__(self, url, data, access_token=None, config=None, max_retries=5):
        self.url = url
        self.data = data
        self.max_retries = max_retries

        if access_token is None:
            self.access_token = SentinelHubSession(config=config)._token["access_token"]  # Fetches the token
        else:
            self.access_token = access_token

    def get_headers(self):
        return {"content-type": "application/json", "Authorization": f"Bearer {self.access_token}"}

    def fetch(self):
        r = self.make_request()
        r.raise_for_status()

        if is_reporting_needed():
            pu_spent = r.headers["x-processingunits-spent"]
            report_usage(pu_spent)

        return r.content

    def with_rate_limiting(request_func):
        @functools.wraps(request_func)
        def handle_rate_limiting(self):
            if not self.has_rate_limiting_with_backoff():
                return request_func(self)

            for retry in range(self.max_retries):
                r = request_func(self)

                if r.status_code == 200:
                    return r
                elif r.status_code == 429:
                    delay = int(r.headers["retry-after"])
                    time.sleep(delay)
                else:
                    r.raise_for_status()

            raise Internal(f"Out of retries. Request to Sentinel Hub failed: {r.text}")

        return handle_rate_limiting

    @with_rate_limiting
    def make_request(self):
        return requests.post(self.url, data=json.dumps(self.data), headers=self.get_headers())

    def has_rate_limiting_with_backoff(self):
        if self.url.startswith(SentinelhubDeployments.USWEST):
            return True
        return False
