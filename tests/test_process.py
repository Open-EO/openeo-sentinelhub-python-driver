import json
import pytest
import responses
import re


import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app


@pytest.fixture
def app_client():
    app.testing = True
    return app.test_client()


###################################

@responses.activate
def test_process_load_collection(app_client):
    """
        Test load_collection process
    """

    # mock response from sentinel-hub:
    sh_url_regex = re.compile('^.*sentinel-hub.com/.*$')
    responses.add(
        responses.GET,
        sh_url_regex,
        body='asdf',
        match_querystring=True,
        status=200,
    )

    data = {
        "process_graph": {
            "loadco1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "Sentinel-1",
                    "spatial_extent": {
                        "west": 16.1,
                        "east": 16.6,
                        "north": 48.6,
                        "south": 47.2
                    },
                    "temporal_extent": ["2017-01-01", "2017-02-01"],
                },
                "result": True,
            },
        },
    }
    r = app_client.post('/result', data=json.dumps(data), content_type='image/png')
    assert r.status_code == 200
    assert r.data == b'asdf'
