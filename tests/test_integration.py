import json
import pytest

import sys, os
os.environ["DYNAMODB_LOCAL_URL"] = "http://dynamodb:8000"
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app

@pytest.fixture
def app_client():
    app.testing = True
    return app.test_client()


###################################

def test_root(app_client):
    """
        Test root ('/') endpoint:
          - response must contain all the required keys
          - list of endpoints must contain at least ourselves
    """
    r = app_client.get('/')

    assert r.status_code == 200
    actual = json.loads(r.data.decode('utf-8'))

    # response must contain all the required keys:
    required_keys = [
        "api_version",
        "backend_version",
        "title",
        "description",
        "endpoints",
    ]
    for k in required_keys:
        assert k in actual

    # list of endpoints must contain at least ourselves:
    expected_endpoint = {
        "path": "/",
        "methods": ["GET"],
    }
    assert expected_endpoint in actual["endpoints"]
