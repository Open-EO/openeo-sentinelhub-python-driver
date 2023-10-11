import os
import json
import requests
import datetime
import time
from logging import log, ERROR

from openeoerrors import Internal


class UsageReporting:
    def __init__(self):
        self.auth_url = os.environ.get("USAGE_REPORTING_AUTH_URL")
        self.auth_client_id = os.environ.get("USAGE_REPORTING_AUTH_CLIENT_ID")
        self.auth_client_secret = os.environ.get("USAGE_REPORTING_AUTH_CLIENT_SECRET")
        self.base_url = os.environ.get("USAGE_REPORTING_BASE_URL")

        self.authenticate()

    def authenticate(self, max_tries=5):
        for try_number in range(max_tries):
            r = requests.post(
                self.auth_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.auth_client_id,
                    "client_secret": self.auth_client_secret,
                },
            )

            if r.status_code >= 200 and r.status_code <= 299:
                j = r.json()
                self.auth_token = {
                    "access_token": j.get("access_token"),
                    "valid_until": time.time() + j.get("expires_in") - 5,
                }

                return
            else:
                log(ERROR, f"Error authenticating for usage reporting on try #{try_number+1}: {r.status_code} {r.text}")
                raise Internal(
                    f"Problems authenticating for usage reporting on try #{try_number+1}: {r.status_code} {r.text}"
                )

        raise Internal(f"Out of retries. Reporting usage failed: {r.status_code} {r.text}")

    def get_token(self):
        if "valid_until" not in self.auth_token or self.auth_token["valid_until"] <= time.time():
            self.authenticate()

        return self.auth_token

    def reporting_check_health(self):
        check_health_url = f"{self.base_url}health"

        r = requests.get(check_health_url)
        content = r.json()

        return r.status_code == 200 and content["status"] == "ok"

    def get_leftover_credits(self, max_tries=5):
        user_url = f"{self.base_url}user"
        reporting_token = self.get_token()

        headers = {"content-type": "application/json", "Authorization": f"Bearer {reporting_token['access_token']}"}

        if not self.reporting_check_health():
            log(ERROR, "Services for usage reporting are not healthy")
            raise Internal("Services for usage reporting are not healthy")

        for try_number in range(max_tries):
            r = requests.get(user_url, headers=headers)

            if r.status_code == 200:
                content = r.json()
                credits = content.get("credits")

                return credits
            else:
                log(ERROR, f"Error fetching leftover credits on try #{try_number+1}: {r.status_code} {r.text}")
                raise Internal(
                    f"Problems during fetching leftover credits on try #{try_number+1}: {r.status_code} {r.text}"
                )

        raise Internal(f"Out of retries. Fetching leftover credits failed: {r.status_code} {r.text}")

    def report_usage(self, user_id, pu_spent, job_id=None, max_tries=5):
        reporting_token = self.get_token()

        reporting_url = f"{self.base_url}resources"

        iso8601_utc_timestamp = (
            datetime.datetime.utcnow().replace(microsecond=0, tzinfo=datetime.timezone.utc).isoformat()
        )
        headers = {"content-type": "application/json", "Authorization": f"Bearer {reporting_token['access_token']}"}
        data = {
            "jobId": job_id if job_id else f"{user_id}_{iso8601_utc_timestamp}",
            "userId": user_id,
            "sourceId": "sentinel-hub-openeo",
            "state": "FINISHED",
            "status": "SUCCEEDED",
            "orchestrator": "openeo",
            "metrics": {"processing": {"value": pu_spent, "unit": "shpu"}},
        }

        if not self.reporting_check_health():
            log(ERROR, "Services for usage reporting are not healthy")
            raise Internal("Services for usage reporting are not healthy")

        for try_number in range(max_tries):
            r = requests.post(reporting_url, data=json.dumps(data), headers=headers)

            if r.status_code >= 200 and r.status_code <= 299:
                return

            else:
                log(ERROR, f"Error reporting usage on try #{try_number+1}: {r.status_code} {r.text}")
                raise Internal(f"Problems during usage reporting on try #{try_number+1}: {r.status_code} {r.text}")

        raise Internal(f"Out of retries. Reporting usage failed: {r.status_code} {r.text}")


usageReporting = UsageReporting()
