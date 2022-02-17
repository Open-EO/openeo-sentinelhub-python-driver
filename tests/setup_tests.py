import base64
import glob
import json
import os
import sys
import time
import re

import pytest
import requests
import responses
import numpy as np


sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rest"))
from app import app
from dynamodb import JobsPersistence, ProcessGraphsPersistence, ServicesPersistence
from openeocollections import collections
from processing.process import Process


FIXTURES_FOLDER = os.path.join(os.path.dirname(__file__), "fixtures")


def load_collections_fixtures(folder, wildcard="*"):
    collections = {}
    files = glob.iglob(folder + wildcard + ".json")
    for file in files:
        with open(file) as f:
            data = json.load(f)
            collections[data["id"]] = data

    return collections


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
