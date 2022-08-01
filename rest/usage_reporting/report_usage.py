import os
import json
import requests
from flask import g
import datetime
import time
from logging import log, ERROR

from openeoerrors import Internal


reporting_token = {}


def is_reporting_needed():
    user_info = g.user.get_user_info()
    return "info" in user_info and "oidc_userinfo" in user_info["info"]


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
        log(ERROR, f"Error authenticating for usage reporting: {r.text}")
        raise Internal(f"Problems during usage reporting: {r.text}")

    j = r.json()

    global reporting_token
    reporting_token = {"access_token": j.get("access_token"), "valid_until": time.time() - 5 + j.get("expires_in")}


def report_usage(pu_spent, job_id=None):
    if "valid_until" not in reporting_token or reporting_token["valid_until"] <= time.time():
        reporting_authenticate()

    reporting_url = os.environ.get("USAGE_REPORTING_URL")
    iso8601_utc_timestamp = datetime.datetime.utcnow().replace(microsecond=0, tzinfo=datetime.timezone.utc).isoformat()
    headers = {"content-type": "application/json", "Authorization": f"Bearer {reporting_token['access_token']}"}
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
        log(ERROR, f"Error reporting usage: {r.text}")
        raise Internal(f"Problems during usage reporting: {r.text}")
