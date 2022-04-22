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
import numpy as np


sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rest"))
from app import app
from dynamodb import JobsPersistence, ProcessGraphsPersistence, ServicesPersistence
from openeocollections import collections
from authentication.authentication import AuthenticationProvider, authentication_provider
from processing.process import Process
from openeoerrors import TemporalExtentError


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


def setup_function(function):
    ProcessGraphsPersistence.ensure_table_exists()
    JobsPersistence.ensure_table_exists()
    JobsPersistence.ensure_queue_exists()
    ServicesPersistence.ensure_table_exists()
    collections.set_collections(load_collections_fixtures("fixtures/collection_information/"))


def teardown_function(function):
    ProcessGraphsPersistence.clear_table()
    JobsPersistence.clear_table()
    ServicesPersistence.clear_table()
    collections.set_collections(None)
