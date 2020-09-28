import base64
import json
import pytest
import glob

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
    def _generate(base_filename):
        filename = os.path.join(FIXTURES_FOLDER, base_filename)
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
          "temporal_extent": ["2019-08-16", "2019-08-18"],
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
            "process": {
              "process_graph": process_graph,
            },
            "type": service_type,
        }
        r = app_client.post("/services", data=json.dumps(data), content_type='application/json')
        assert r.status_code == 201, r.data
        service_id = r.headers["OpenEO-Identifier"]
        return service_id
    return wrapped


@pytest.fixture
def authorization_header(app_client):
    SH_CLIENT_ID = os.environ.get('TESTS_SH_CLIENT_ID', None)
    SH_CLIENT_SECRET = os.environ.get('TESTS_SH_CLIENT_SECRET', None)
    if not SH_CLIENT_ID or not SH_CLIENT_SECRET:
        raise Exception("This test needs TESTS_SH_CLIENT_ID and TESTS_SH_CLIENT_SECRET env vars to be set.")

    r = app_client.get("/credentials/basic", headers={
        "Authorization": "Basic " + base64.b64encode(bytes(f"{SH_CLIENT_ID}:{SH_CLIENT_SECRET}", "utf-8")).decode("utf-8"),
    })
    assert r.status_code == 200, r.data
    j = r.json
    return f'Bearer basic//{j["access_token"]}'


def setup_function(function):
    ProcessGraphsPersistence.ensure_table_exists()
    JobsPersistence.ensure_table_exists()
    JobsPersistence.ensure_queue_exists()
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
        "process": {
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
        },
    }

    r = app_client.post("/jobs", data=json.dumps(data), content_type='application/json')

    assert r.status_code == 201

    record_id = r.headers["OpenEO-Identifier"]

    r = app_client.get("/jobs/{}".format(record_id))
    actual = json.loads(r.data.decode('utf-8'))

    assert r.status_code == 200
    assert actual["status"] == "created"
    assert actual["process"]["process_graph"] == data["process"]["process_graph"]
    assert actual["id"] == record_id

    bbox2 = {
        "west": 12.1,
        "east": 12.6,
        "north": 42.6,
        "south": 41.2
    }
    data2 = {
        "process": {
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
        },
        "title": "Load collection test"
    }

    r = app_client.patch("/jobs/{}".format(record_id), data=json.dumps(data2), content_type='application/json')

    assert r.status_code == 204

    r = app_client.get("/jobs/{}".format(record_id))
    actual = json.loads(r.data.decode('utf-8'))

    assert r.status_code == 200
    assert actual["process"]["process_graph"] == data2["process"]["process_graph"]
    assert actual["title"] == data2["title"]

    r = app_client.delete("/jobs/{}".format(record_id))

    assert r.status_code == 204

    r = app_client.get("/jobs/{}".format(record_id))

    assert r.status_code == 404


def test_process_batch_job(app_client, example_process_graph, authorization_header):
    """
         - test /jobs/job_id/results endpoints
    """
    data = {
        "process": {
          "process_graph": example_process_graph,
        }
    }
    r = app_client.post("/jobs", data=json.dumps(data), content_type='application/json')
    assert r.status_code == 201
    job_id = r.headers["OpenEO-Identifier"]

    r = app_client.delete(f"/jobs/{job_id}/results")
    assert r.status_code == 204

    # without authorization header, this call fails:
    r = app_client.post(f"/jobs/{job_id}/results")
    assert r.status_code == 401

    r = app_client.post(f"/jobs/{job_id}/results", headers={"Authorization": authorization_header})
    assert r.status_code == 202

    r = app_client.post(f"/jobs/{job_id}/results", headers={"Authorization": authorization_header})
    actual = json.loads(r.data.decode('utf-8'))
    assert r.status_code == 400
    assert actual["code"] == "JobLocked"

    r = app_client.get(f"/jobs/{job_id}")
    actual = json.loads(r.data.decode('utf-8'))
    assert r.status_code == 200
    assert actual["status"] in ["queued", "running", "error", "finished"]

    r = app_client.get(f"/jobs/{job_id}/results")
    actual = json.loads(r.data.decode('utf-8'))
    assert r.status_code == 400
    assert  actual["code"] == "JobNotFinished"

    r = app_client.delete(f"/jobs/{job_id}/results")
    assert r.status_code == 204


def test_result(app_client, example_process_graph, authorization_header):
    """
         - test /result endpoint
    """
    data = {
        "process": {
          "process_graph": example_process_graph,
        }
    }

    r = app_client.post('/result', data=json.dumps(data), content_type='application/json')
    assert r.status_code == 401

    r = app_client.post('/result', data=json.dumps(data), content_type='application/json', headers={"Authorization": authorization_header})
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
        "process": {
          "process_graph": example_process_graph,
        },
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
        "costs": 0,
        "budget": None,
        "configuration": {}
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
        "process": {
          "process_graph": example_process_graph,
        },
        "attributes": {},
        "created": actual["created"],
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


@pytest.mark.skip("Without width/height (just resx/y) the dimensions are not 100% the same as with OGC services. We should still try to fix it better.")
def test_reduce(app_client, get_expected_data):
    """
         - test /result endpoint with reduce_dimension process
    """
    data = {
        "process": {
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
                "process_id": "reduce_dimension",
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
        }

    r = app_client.post('/result', data=json.dumps(data), content_type='application/json')
    assert r.status_code == 200

    expected_data = get_expected_data("test_reduce.tiff")
    assert r.data == expected_data

@pytest.mark.skip("TIFF32f is no longer returned")
def test_xyz_service(app_client, service_factory, example_process_graph_with_variables, get_expected_data):
    service_id = service_factory(example_process_graph_with_variables, title="Test XYZ service", service_type="xyz")

    # $ python globalmaptiles.py 13 42.0 12.3
    #   13/4375/5150 ( TileMapService: z / x / y )
    # 	Google: 4375 3041
    zoom, tx, ty = 13, 4375, 3041
    r = app_client.get('/service/xyz/{}/{}/{}/{}'.format(service_id, int(zoom), int(tx), int(ty)))
    assert r.status_code == 200
    expected_data = get_expected_data("tile256x256.tiff")
    assert r.data == expected_data


def test_xyz_service_2(app_client, service_factory, get_expected_data, authorization_header):
    process_graph = {
      "loadco1": {
        "process_id": "load_collection",
        "arguments": {
          "id": "S2L1C",
          "spatial_extent": {
            "west": {
              "variable_id": "spatial_extent_west"
            },
            "east": {
              "variable_id": "spatial_extent_east"
            },
            "north": {
              "variable_id": "spatial_extent_north"
            },
            "south": {
              "variable_id": "spatial_extent_south"
            }
          },
          "temporal_extent": [
            "2019-08-01",
            "2019-08-18"
          ],
          "options": {
            "width": {
              "variable_id": "tile_size"
            },
            "height": {
              "variable_id": "tile_size"
            }
          }
        }
      },
      "ndvi1": {
        "process_id": "ndvi",
        "arguments": {
          "data": {
            "from_node": "loadco1"
          }
        }
      },
      "reduce1": {
        "process_id": "reduce_dimension",
        "arguments": {
          "data": {
            "from_node": "ndvi1"
          },
          "reducer": {
            "callback": {
              "2": {
                "process_id": "mean",
                "arguments": {
                  "data": {
                    "from_argument": "data"
                  }
                },
                "result": True
              }
            }
          },
          "dimension": "t"
        }
      },
      "linear1": {
        "process_id": "linear_scale_range",
        "arguments": {
          "x": {
            "from_node": "reduce1"
          },
          "inputMin": 0,
          "inputMax": 1,
          "outputMax": 255
        }
      },
      "result1": {
        "process_id": "save_result",
        "arguments": {
          "data": {
            "from_node": "linear1"
          },
          "format": "JPEG",
          "options": {
            "datatype": "byte"
          }
        },
        "result": True
      }
    }

    service_id = service_factory(process_graph, title="Test XYZ service", service_type="xyz")

    zoom, tx, ty = 14, 8660, 5908

    r = app_client.get(f'/service/xyz/{service_id}/{int(zoom)}/{int(tx)}/{int(ty)}')
    assert r.status_code == 401, r.data

    r = app_client.get(f'/service/xyz/{service_id}/{int(zoom)}/{int(tx)}/{int(ty)}', headers={"Authorization": authorization_header})
    assert r.status_code == 200, r.data
    expected_data = get_expected_data("tile256x256ndvi.jpeg")
    assert r.data == expected_data, "File is not the same!"


@pytest.mark.parametrize('value,double_value,expected_status_code', [
    (0.5, 1.0, 200),
    (0.5, 2.0, 400),
])
def test_assert_works(app_client, value, double_value, expected_status_code, authorization_header):
    process_graph = {
      "gencol1": {
        "process_id": "create_cube",
        "arguments": {
          "data": [
            [
              [
                [value, 0.15],
              ],
              [
                [0.15, None]
              ]
            ]
          ],
          "dims": ["y", "x", "t", "band"],
          "coords": {
            "y": [12.3],
            "x": [45.1, 45.2],
            "t": ["2019-08-01 11:00:12"],
            "band": ["nir", "red"]
          }
        },
      },
      "linear1": {
        "process_id": "linear_scale_range",
        "arguments": {
          "x": {
            "from_node": "gencol1"
          },
          "inputMin": 0.0,
          "inputMax": 1.0,
          "outputMin": 0.0,
          "outputMax": 2.0,
        }
      },
      "expectedlinear1": {
        "process_id": "create_cube",
        "arguments": {
          "data": [
            [
              [
                [double_value, 0.3],
              ],
              [
                [0.3, None]
              ]
            ]
          ],
          "dims": ["y", "x", "t", "band"],
          "coords": {
            "y": [12.3],
            "x": [45.1, 45.2],
            "t": ["2019-08-01 11:00:12"],
            "band": ["nir", "red"]
          }
        }
      },
      "assertlinear1": {
        "process_id": "assert_equals",
        "arguments": {
          "a": {
            "from_node": "linear1"
          },
          "b": {
            "from_node": "expectedlinear1"
          }
        },
      },
      "result1": {
        "process_id": "save_result",
        "arguments": {
          "data": {
            "from_node": "gencol1"
          },
          "format": "gtiff",
          "options": {
            "datatype": "float32"
          }
        },
        "result": True
      }
    }

    data = {
        "process": {
          "process_graph": process_graph,
        }
    }
    r = app_client.post('/result', data=json.dumps(data), content_type='application/json', headers={"Authorization": authorization_header})
    assert r.status_code == expected_status_code, r.data


def _get_test_process_graphs():
    for f in glob.glob(os.path.join(os.path.dirname(__file__), "test_process_graphs/*.json")):
        if not os.path.isfile(f) or os.path.basename(f).startswith('_'):
            print("Skipping: {}".format(os.path.basename(f)))
            continue
        with open(f, "rt") as f:
            c = f.read()
            print(c)
            yield c

@pytest.mark.parametrize('process_graph_json', _get_test_process_graphs())
def test_run_test_process_graphs(app_client, process_graph_json, authorization_header):
    """
        Load process graph definitions from test_process_graph/*.json and execute them
        via POST /result/, expecting status 200 on each of them.
    """
    process_graph = json.loads(process_graph_json)
    data = {
        "process": {
          "process_graph": process_graph,
        }
    }
    r = app_client.post('/result', data=json.dumps(data), content_type='application/json', headers={"Authorization": authorization_header})
    assert r.status_code == 200, r.data


def test_process_graph_api(app_client, example_process_graph):
    """
        Get /process_graphs/ (must be empty), test CRUD operations.
    """
    # get a list of process graphs, should be empty:
    r = app_client.get('/process_graphs')
    assert r.status_code == 200, r.data
    expected = []
    actual = json.loads(r.data.decode('utf-8')).get("processes")
    assert actual == expected

    # Use invalid process graph id:
    process_graph_id = "c91ea247-2ec0-4048-ab6c-1c31c3ecfa7e"
    data = {
        "summary": "invalid id",
        "process_graph": example_process_graph,
    }
    r = app_client.put(f'/process_graphs/{process_graph_id}', data=json.dumps(data), content_type='application/json')
    assert r.status_code == 400, r.data

    # create a process graph:
    process_graph_id = "testing_process_graph"
    data = {
        "summary": "test",
        "process_graph": example_process_graph,
    }
    r = app_client.put(f'/process_graphs/{process_graph_id}', data=json.dumps(data), content_type='application/json')
    assert r.status_code == 200, r.data

    # get a list of process graphs again:
    r = app_client.get('/process_graphs')
    assert r.status_code == 200, r.data
    expected = [
        {
            "id": process_graph_id,
            "summary": "test",
        },
    ]
    actual = json.loads(r.data.decode('utf-8')).get("processes")
    assert actual == expected

    # get the process graph:
    r = app_client.get('/process_graphs/{}'.format(process_graph_id))
    assert r.status_code == 200, r.data
    expected = {
        "id": process_graph_id,
        "summary": "test",
        "process_graph": example_process_graph,
        "description": None,
    }
    actual = json.loads(r.data.decode('utf-8'))
    assert actual == expected

    # change it:
    data = {
        "summary": "test2",
        "description": "asdf",
        "process_graph": example_process_graph,
    }
    r = app_client.put('/process_graphs/{}'.format(process_graph_id), data=json.dumps(data), content_type='application/json')
    assert r.status_code == 200, r.data

    # get the process graph again:
    r = app_client.get('/process_graphs/{}'.format(process_graph_id))
    assert r.status_code == 200, r.data
    expected = {
        "id": process_graph_id,
        "summary": "test2",
        "description": "asdf",
        "process_graph": example_process_graph,
    }
    actual = json.loads(r.data.decode('utf-8'))
    assert actual == expected

    # delete it:
    r = app_client.delete('/process_graphs/{}'.format(process_graph_id))
    assert r.status_code == 204, r.data

    # make sure the record is removed:
    r = app_client.get('/process_graphs/{}'.format(process_graph_id))
    assert r.status_code == 404
    r = app_client.get('/process_graphs')
    assert r.status_code == 200, r.data
    expected = []
    actual = json.loads(r.data.decode('utf-8')).get("processes")
    assert actual == expected
