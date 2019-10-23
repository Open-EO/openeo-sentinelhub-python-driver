import json
import pytest

import sys, os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rest"))
from app import app
from dynamodb import JobsPersistence, ProcessGraphsPersistence, ServicesPersistence


FIXTURES_FOLDER = os.path.join(os.path.dirname(__file__), 'fixtures')


@pytest.fixture
def app_client():
    # set env vars used by the app:
    os.environ["BACKEND_VERSION"] = 'v6.7.8'
    app.testing = True
    return app.test_client()


@pytest.fixture
def get_expected_data():
    def _generate(file):
        filename = os.path.join(FIXTURES_FOLDER, file)
        with open(filename, 'rb') as f:
            result = f.read()
        return result
    return _generate


@pytest.fixture
def example_process_graph():
    return {
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
          "temporal_extent": ["2019-08-16", "2019-08-18"]
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


@pytest.fixture
def example_process_graph_with_variables():
    return {
      "loadco1": {
      "process_id": "load_collection",
        "arguments": {
          "id": "S2L1C",
          "spatial_extent": {
            "west": {"variable_id": "spatial_extent_west"},
            "east": {"variable_id": "spatial_extent_east"},
            "north": {"variable_id": "spatial_extent_north"},
            "south": {"variable_id": "spatial_extent_south"}
          },
          "temporal_extent": ["2019-08-16", "2019-08-18"],
          "options": {
            "width": {"variable_id": "tile_size"},
            "height": {"variable_id": "tile_size"}
          }
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


@pytest.fixture
def service_factory(app_client):
    def wrapped(process_graph, title="MyService", service_type="xyz"):
        data = {
            "title": title,
            "process_graph": process_graph,
            "type": service_type,
        }
        r = app_client.post("/services", data=json.dumps(data), content_type='application/json')
        assert r.status_code == 201
        service_id = r.headers["OpenEO-Identifier"]
        return service_id
    return wrapped


def setup_function(function):
    ProcessGraphsPersistence.ensure_table_exists()
    JobsPersistence.ensure_table_exists()
    ServicesPersistence.ensure_table_exists()


def teardown_function(function):
    ProcessGraphsPersistence.clear_table()
    JobsPersistence.clear_table()
    ServicesPersistence.clear_table()


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

    # version must be correctly read from env vars:
    assert actual["backend_version"] == '6.7.8'

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

    assert r.status_code == 204

    r = app_client.get("/jobs/{}".format(record_id))
    actual = json.loads(r.data.decode('utf-8'))

    assert r.status_code == 200
    assert actual["process_graph"] == data2["process_graph"]
    assert actual["title"] == data2["title"]

    r = app_client.delete("/jobs/{}".format(record_id))

    assert r.status_code == 204

    r = app_client.get("/jobs/{}".format(record_id))

    assert r.status_code == 404


def test_process_batch_job(app_client, example_process_graph):
    """
         - test /jobs/job_id/results endpoints
    """
    data = {
        "process_graph": example_process_graph,
    }
    r = app_client.post("/jobs", data=json.dumps(data), content_type='application/json')
    assert r.status_code == 201
    record_id = r.headers["OpenEO-Identifier"]

    r = app_client.delete("/jobs/{}/results".format(record_id))
    actual = json.loads(r.data.decode('utf-8'))
    assert r.status_code == 400
    assert actual["code"]  == "JobNotStarted"

    r = app_client.post("/jobs/{}/results".format(record_id))
    assert r.status_code == 202

    r = app_client.post("/jobs/{}/results".format(record_id))
    actual = json.loads(r.data.decode('utf-8'))
    assert r.status_code == 400
    assert actual["code"] == "JobLocked"

    r = app_client.get("/jobs/{}".format(record_id))
    actual = json.loads(r.data.decode('utf-8'))
    assert r.status_code == 200
    assert actual["status"] in ["queued"]

    r = app_client.get("/jobs/{}/results".format(record_id))
    actual = json.loads(r.data.decode('utf-8'))
    assert r.status_code == 400
    assert  actual["code"] == "JobNotFinished"

    r = app_client.delete("/jobs/{}/results".format(record_id))
    assert r.status_code == 200


def test_result(app_client, example_process_graph):
    """
         - test /result endpoint
    """
    data = {
        "process_graph": example_process_graph,
    }
    r = app_client.post('/result', data=json.dumps(data), content_type='application/json')
    assert r.status_code == 200


def test_services_crud(app_client, example_process_graph):
    """
         - test /services endpoint
    """
    r = app_client.get("/services")
    expected = []
    actual = json.loads(r.data.decode('utf-8')).get("services")
    assert r.status_code == 200
    assert actual == expected

    data = {
        "title": "MyService",
        "process_graph": example_process_graph,
        "type": "xyz",
    }
    r = app_client.post("/services", data=json.dumps(data), content_type='application/json')
    assert r.status_code == 201
    service_id = r.headers["OpenEO-Identifier"]

    r = app_client.get("/services")
    assert r.status_code == 200
    services = json.loads(r.data.decode('utf-8')).get("services")
    assert len(services) == 1
    expected = {
        "id": service_id,
        "title": data["title"],
        "description": None,
        "url": "http://localhost/service/xyz/{}/{{z}}/{{x}}/{{y}}".format(service_id),
        "type": data["type"],
        "enabled": True,
        "plan": None,
        "costs": 0,
        "budget": None,
    }
    assert services[0] == expected

    patch_data = {
        "title": "MyService2",
    }
    r = app_client.patch("/services/{}".format(service_id), data=json.dumps(patch_data), content_type='application/json')
    assert r.status_code == 204

    expected.update(patch_data)

    r = app_client.get("/services")
    assert r.status_code == 200
    services = json.loads(r.data.decode('utf-8')).get("services")
    assert len(services) == 1
    assert services[0] == expected

    r = app_client.get("/services/{}".format(service_id))
    assert r.status_code == 200
    actual = json.loads(r.data.decode('utf-8'))
    # get record supports additional fields:
    expected.update({
        "process_graph": example_process_graph,
        "parameters": {},
        "attributes": {},
        "submitted": actual["submitted"],
    })
    assert actual == expected

    # delete service and make sure it is deleted:
    r = app_client.delete("/services/{}".format(service_id))
    assert r.status_code == 204

    r = app_client.get("/services/{}".format(service_id))
    assert r.status_code == 404

    r = app_client.get("/services")
    expected = []
    actual = json.loads(r.data.decode('utf-8')).get("services")
    assert r.status_code == 200
    assert actual == expected


def test_reduce(app_client, get_expected_data):
    """
         - test /result endpoint with reduce process
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
                "temporal_extent": ["2019-08-16", "2019-08-25"]
              }
            },
            "reduce1": {
              "process_id": "reduce",
              "arguments": {
                "data": {"from_node": "loadco1"},
                "dimension": "t",
                "reducer": {
                    "callback": {
                        "min": {
                          "process_id": "min",
                          "arguments": {
                            "data": {"from_argument": "data"}
                          },
                        },
                        "mean": {
                          "process_id": "mean",
                          "arguments": {
                            "data": {"from_argument": "data"}
                          },
                        },
                        "sum": {
                          "process_id": "sum",
                          "arguments": {
                            "data": [{"from_node": "min"},{"from_node": "mean"}]
                          },
                          "result": True
                        }
                    }
                }
              }
            },
            "result1": {
              "process_id": "save_result",
              "arguments": {
                "data": {"from_node": "reduce1"},
                "format": "gtiff"
              },
              "result": True
            }
          }
        }

    r = app_client.post('/result', data=json.dumps(data), content_type='application/json')
    assert r.status_code == 200

    expected_data = get_expected_data("test_reduce.tiff")
    assert r.data == expected_data

def test_xyz_service(app_client, service_factory, example_process_graph_with_variables, get_expected_data):
    service_id = service_factory(example_process_graph_with_variables, title="Test XYZ service", service_type="xyz")

    # $ python globalmaptiles.py 13 42.0 12.3
    #   13/4375/5150 ( TileMapService: z / x / y )
    # 	Google: 4375 3041
    zoom = 13
    tx = 4375
    ty = 5150
    r = app_client.get('/service/xyz/{}/{}/{}/{}'.format(service_id, int(zoom), int(tx), int(ty)))
    assert r.status_code == 200
    expected_data = get_expected_data("tile256x256.tiff")
    assert r.data == expected_data
