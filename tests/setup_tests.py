import base64
import glob
import json
import os
import sys
import time
import re
from functools import wraps

import pytest
import requests
import responses
from responses import matchers
import numpy as np
from sentinelhub import BBox, DataCollection, MimeType, CRS


sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rest"))
from app import app
from dynamodb import JobsPersistence, ProcessGraphsPersistence, ServicesPersistence
from openeo_collections.collections import collections, CollectionsProvider
from authentication.authentication import AuthenticationProvider, authentication_provider
from processing.process import Process
from processing.sentinel_hub import SentinelHub
from processing.processing import delete_batch_job
from openeoerrors import ProcessGraphComplexity


FIXTURES_FOLDER = os.path.join(os.path.dirname(__file__), "fixtures")


def load_collections_fixtures(folder, wildcard="*"):
    collections = {}
    files = glob.iglob(folder + wildcard + ".json")
    for file in files:
        with open(file) as f:
            data = json.load(f)
            collections[data["id"]] = data

    return collections


def with_mocked_auth(func):
    """
    Adds mocked responses for OIDC auth with EGI client. Passes through other requests.
    """

    @wraps(func)
    @responses.activate
    def decorated_function(*args, **kwargs):
        responses.add(
            responses.GET,
            "https://aai.egi.eu/oidc/.well-known/openid-configuration",
            json={"userinfo_endpoint": "http://dummy_userinfo_endpoint"},
        )
        responses.add(
            responses.GET,
            "http://dummy_userinfo_endpoint",
            json={
                "sub": "example-id",
                "eduperson_entitlement": [
                    "urn:mace:egi.eu:group:vo.openeo.cloud:role=vm_operator#aai.egi.eu",
                    "urn:mace:egi.eu:group:vo.openeo.cloud:role=member#aai.egi.eu",
                    "urn:mace:egi.eu:group:vo.openeo.cloud:role=early_adopter#aai.egi.eu",
                ],
            },
        )
        responses.add_passthru(re.compile(".*"))
        return func(*args, **kwargs)

    return decorated_function


valid_sh_token = None


def set_valid_sh_token():
    global valid_sh_token

    if valid_sh_token is not None:
        return

    SH_CLIENT_ID = os.environ.get("SH_CLIENT_ID", None)
    SH_CLIENT_SECRET = os.environ.get("SH_CLIENT_SECRET", None)
    if not SH_CLIENT_ID or not SH_CLIENT_SECRET:
        raise Exception("This test needs SH_CLIENT_ID and SH_CLIENT_SECRET env vars to be set.")

    r = requests.post(
        "https://services.sentinel-hub.com/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": SH_CLIENT_ID,
            "client_secret": SH_CLIENT_SECRET,
        },
    )
    r.raise_for_status()
    j = r.json()
    valid_sh_token = j["access_token"]


set_valid_sh_token()


@pytest.fixture
def get_process_graph():
    def wrapped(
        bands=None,
        collection_id=None,
        spatial_extent=None,
        temporal_extent=["2017-01-01", "2017-02-01"],
        file_format="gtiff",
        options=None,
        featureflags=None,
    ):
        process_graph = {
            "loadco1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": collection_id,
                    "temporal_extent": temporal_extent,
                    "spatial_extent": spatial_extent,
                },
            },
            "result1": {
                "process_id": "save_result",
                "arguments": {
                    "data": {"from_node": "loadco1"},
                    "format": file_format,
                },
                "result": True,
            },
        }
        if bands:
            process_graph["loadco1"]["arguments"]["bands"] = bands
        if spatial_extent:
            process_graph["loadco1"]["arguments"]["spatial_extent"] = spatial_extent
        if featureflags:
            process_graph["loadco1"]["arguments"]["featureflags"] = featureflags
        if options:
            process_graph["result1"]["arguments"]["options"] = options

        return process_graph

    return wrapped


def setup_function(function):
    ProcessGraphsPersistence.ensure_table_exists()
    JobsPersistence.ensure_table_exists()
    ServicesPersistence.ensure_table_exists()
    collections.set_collections(load_collections_fixtures("fixtures/collection_information/"))


def teardown_function(function):
    ProcessGraphsPersistence.clear_table()
    JobsPersistence.clear_table()
    ServicesPersistence.clear_table()
    collections.set_collections(None)
