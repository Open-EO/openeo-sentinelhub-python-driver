import os
import json
import requests
from flask import g
import datetime

# url
# https://etl-dev.terrascope.be/resources

# example
# {
#     "jobId": "TEST",
#     "userId": "bramjanssen",
#     "sourceId": "MEP",
#     "state": "FINISHED",
#     "status": "SUCCEEDED",
#     "orchestrator": "openeo",
#     "metrics": {
#         "processing": {
#             "value": 1000,
#             "unit": "shpu"
#         }
#     }
# }

# REQUIRED FIELDS
# - jobId
# - executionId
# - userId
# - sourceId
# - state (one of [ ACCEPTED, RUNNING, FINISHED, KILLED, FAILED, UNDEFINED ])
# - status (one of [ SUCCEEDED, FAILED, KILLED, UNDEFINED ])
# - metrics
#   - processing
#     - value
#     - unit (shpu)


def reporting_authenticate():
    auth_url = os.environ.get("USAGE_REPORTING_AUTH_URL")
    auth_client_id = os.environ.get("USAGE_REPORTING_AUTH_CLIENT_ID")
    auth_client_secret = os.environ.get("USAGE_REPORTING_AUTH_CLIENT_SECRET")

    r = requests.post(
        auth_url,
        data={
            "grant_type": "client_credentials",
            "client_id": auth_client_id,
            "client_secret": auth_client_secret,
        },
    )

    if r.status_code != 200:
        print("ERROR AUTHENTICATING for reporting")
        print(r.status_code, r.text)

    j = r.json()
    return j.get("access_token")


def report_usage(pu_spent, job_id=None):
    reporting_token = reporting_authenticate()
    reporting_url = os.environ.get("USAGE_REPORTING_URL")

    iso8601_utc_timestamp = datetime.datetime.utcnow().replace(microsecond=0, tzinfo=datetime.timezone.utc).isoformat()
    headers = {"content-type": "application/json", "Authorization": f"Bearer {reporting_token}"}

    data = {
        "jobId": job_id if job_id else f"{g.user.user_id}_{iso8601_utc_timestamp}",
        "userId": g.user.user_id,
        "sourceId": "sentinel-hub-openeo",
        "state": "FINISHED",
        "status": "SUCCEEDED",
        "orchestrator": "openeo",
        "metrics": {"processing": {"value": pu_spent, "unit": "shpu"}},
    }

    r = requests.post(reporting_url, data=json.dumps(data), headers=headers)

    if r.status_code != 200:
        print("ERROR reporting")
        print(r.status_code, r.text)
