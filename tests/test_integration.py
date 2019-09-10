import json
import pytest

import sys, os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rest"))
from app import app
from dynamodb import Persistence


@pytest.fixture
def app_client():
    app.testing = True
    return app.test_client()

def setup_function(function):
    Persistence.ensure_table_exists(Persistence.ET_PROCESS_GRAPHS)
    Persistence.ensure_table_exists(Persistence.ET_JOBS, True)


def teardown_function(function):
    Persistence.delete_table(Persistence.ET_PROCESS_GRAPHS)
    Persistence.delete_table(Persistence.ET_JOBS)


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


def test_manage_batch_jobs(app_client):
    """
         - test POST "/jobs"
         - test /jobs/job_id endpoints
    """

    bbox = {
        "west": 16.1,
        "east": 16.6,
        "north": 48.6,
        "south": 47.2
    }
    data = {
        "process_graph": {
            "loadco1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "S2L1C",
                    "spatial_extent": bbox,
                    "temporal_extent": ["2017-01-01", "2017-02-01"],
                },
                "result": True,
            },
        },
    }

    r = app_client.post("/jobs", data=json.dumps(data), content_type='application/json')

    assert r.status_code == 201

    record_id = r.headers["OpenEO-Identifier"]

    r = app_client.get("/jobs/{}".format(record_id))
    actual = json.loads(r.data.decode('utf-8'))

    assert r.status_code == 200
    assert actual["status"] == "submitted"
    assert actual["process_graph"] == data["process_graph"]
    assert actual["id"] == record_id

    bbox2 = {
        "west": 12.1,
        "east": 12.6,
        "north": 42.6,
        "south": 41.2
    }
    data2 = {
        "process_graph": {
            "loadco1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "S2L1C",
                    "spatial_extent": bbox2,
                    "temporal_extent": ["2017-01-01", "2017-03-01"],
                },
                "result": True,
            },
        },
        "title": "Load collection test"
    }

    r = app_client.patch("/jobs/{}".format(record_id), data=json.dumps(data2), content_type='application/json')

    assert r.status == "204 NO CONTENT"

    r = app_client.get("/jobs/{}".format(record_id))
    actual = json.loads(r.data.decode('utf-8'))

    assert r.status_code == 200
    assert actual["process_graph"] == data2["process_graph"]
    assert actual["title"] == data2["title"]

    r = app_client.delete("/jobs/{}".format(record_id))
    
    assert r.status_code == 204

    r = app_client.get("/jobs/{}".format(record_id))

    assert r.status_code == 404

def test_process_batch_job(app_client):
    """
         - test /jobs/job_id/results endpoints
    """

    data = {
        "process_graph": {
            "loadco1": {
            "process_id": "load_collection",
              "arguments": {
                "id": "S2L1C",
                "spatial_extent": {
                  "west": 12.32271,
                  "east": 12.33572,
                  "north": 42.07112,
                  "south": 42.06347
                },
                "temporal_extent": "2019-08-17"
              }
            },
            "ndvi1": {
              "process_id": "ndvi",
              "arguments": {
                "data": {"from_node": "loadco1"}
              }
            },
            "result1": {
              "process_id": "save_result",
              "arguments": {
                "data": {"from_node": "ndvi1"},
                "format": "gtiff"
              },
              "result": True
            }
          }
        }

    r = app_client.post("/jobs", data=json.dumps(data), content_type='application/json')
    assert r.status_code == 201
    record_id = r.headers["OpenEO-Identifier"]

    r = app_client.delete("/jobs/{}/results".format(record_id))
    actual = json.loads(r.data.decode('utf-8'))
    assert r.status_code == 400
    assert actual["message"]  == "Job is not queued or running."

    r = app_client.post("/jobs/{}/results".format(record_id))
    assert r.status_code == 202

    r = app_client.post("/jobs/{}/results".format(record_id))
    actual = json.loads(r.data.decode('utf-8'))
    assert r.status_code == 400
    assert actual["message"] == "Job already queued or running."

    r = app_client.get("/jobs/{}".format(record_id))
    actual = json.loads(r.data.decode('utf-8'))
    assert r.status_code == 200
    assert actual["status"] in ["queued"]

    r = app_client.get("/jobs/{}/results".format(record_id))
    actual = json.loads(r.data.decode('utf-8'))
    assert r.status_code == 503
    assert  actual["message"] == "openEO error: JobNotFinished"

    r = app_client.delete("/jobs/{}/results".format(record_id))
    assert r.status_code == 200

# @pytest.mark.skip(reason="We need to mock the request")
def test_result(app_client):
    """
         - test /result endpoint
    """
    data = {
        "process_graph": {
            "loadco1": {
            "process_id": "load_collection",
              "arguments": {
                "id": "S2L1C",
                "spatial_extent": {
                  "west": 12.32271,
                  "east": 12.33572,
                  "north": 42.07112,
                  "south": 42.06347
                },
                "temporal_extent": "2019-08-17"
              }
            },
            "ndvi1": {
              "process_id": "ndvi",
              "arguments": {
                "data": {"from_node": "loadco1"}
              }
            },
            "result1": {
              "process_id": "save_result",
              "arguments": {
                "data": {"from_node": "ndvi1"},
                "format": "gtiff"
              },
              "result": True
            }
          }
        }

    r = app_client.post('/result', data=json.dumps(data), content_type='application/json')
    # actual = json.loads(r.data.decode('utf-8'))
    # print(r.data)

    assert r.status_code == 200

