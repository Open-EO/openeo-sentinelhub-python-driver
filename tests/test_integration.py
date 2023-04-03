from setup_tests import *


@pytest.fixture
def get_expected_data():
    def _generate(base_filename):
        filename = os.path.join(FIXTURES_FOLDER, base_filename)
        with open(filename, "rb") as f:
            result = f.read()
        return result

    return _generate


@pytest.fixture
def example_process_graph():
    return {
        "loadco1": {
            "process_id": "load_collection",
            "arguments": {
                "id": "sentinel-2-l1c",
                "spatial_extent": {"west": 12.32271, "east": 12.33572, "north": 42.07112, "south": 42.06347},
                "temporal_extent": ["2019-08-16", "2019-08-18"],
                "bands": ["B01", "B02"],
            },
        },
        "mean1": {
            "process_id": "reduce_dimension",
            "arguments": {
                "data": {"from_node": "loadco1"},
                "dimension": "t",
                "reducer": {
                    "process_graph": {
                        "1": {"process_id": "mean", "arguments": {"data": {"from_parameter": "data"}}, "result": True}
                    }
                },
            },
        },
        "result1": {
            "process_id": "save_result",
            "arguments": {"data": {"from_node": "mean1"}, "format": "gtiff"},
            "result": True,
        },
    }


@pytest.fixture
def example_process_graph_with_variables():
    return {
        "loadco1": {
            "process_id": "load_collection",
            "arguments": {
                "id": "sentinel-2-l1c",
                "spatial_extent": {
                    "west": {"from_parameter": "spatial_extent_west"},
                    "east": {"from_parameter": "spatial_extent_east"},
                    "north": {"from_parameter": "spatial_extent_north"},
                    "south": {"from_parameter": "spatial_extent_south"},
                },
                "temporal_extent": ["2019-08-16", "2019-08-18"],
            },
        },
        "ndvi1": {"process_id": "ndvi", "arguments": {"data": {"from_node": "loadco1"}}},
        "result1": {
            "process_id": "save_result",
            "arguments": {"data": {"from_node": "ndvi1"}, "format": "gtiff"},
            "result": True,
        },
    }


@pytest.fixture
def get_example_process_graph_with_bands_and_collection():
    def wrapped(bands, collection_id):
        return {
            "loadco1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": collection_id,
                    "spatial_extent": {"west": 12.32271, "east": 12.33572, "north": 42.07112, "south": 42.06347},
                    "temporal_extent": ["2017-12-31", "2018-01-07"],
                    "bands": bands,
                },
            },
            "mean1": {
                "process_id": "reduce_dimension",
                "arguments": {
                    "data": {"from_node": "loadco1"},
                    "dimension": "t",
                    "reducer": {
                        "process_graph": {
                            "1": {
                                "process_id": "mean",
                                "arguments": {"data": {"from_parameter": "data"}},
                                "result": True,
                            }
                        }
                    },
                },
            },
            "result1": {
                "process_id": "save_result",
                "arguments": {"data": {"from_node": "mean1"}, "format": "gtiff"},
                "result": True,
            },
        }

    return wrapped


@pytest.fixture
def authorization_header(app_client):
    SH_CLIENT_ID = os.environ.get("SH_CLIENT_ID", None)
    SH_CLIENT_SECRET = os.environ.get("SH_CLIENT_SECRET", None)
    if not SH_CLIENT_ID or not SH_CLIENT_SECRET:
        raise Exception("This test needs SH_CLIENT_ID and SH_CLIENT_SECRET env vars to be set.")

    r = app_client.get(
        "/credentials/basic",
        headers={
            "Authorization": "Basic "
            + base64.b64encode(bytes(f"{SH_CLIENT_ID}:{SH_CLIENT_SECRET}", "ascii")).decode("ascii"),
        },
    )
    assert r.status_code == 200, r.data
    j = r.json
    return f'Bearer basic//{j["access_token"]}'


@pytest.fixture
def authorization_header_base64(app_client):
    # same as authorization_header fixture, except that client_secret is base64 encoded:
    SH_CLIENT_ID = os.environ.get("SH_CLIENT_ID", None)
    SH_CLIENT_SECRET = os.environ.get("SH_CLIENT_SECRET", None)
    if not SH_CLIENT_ID or not SH_CLIENT_SECRET:
        raise Exception("This test needs SH_CLIENT_ID and SH_CLIENT_SECRET env vars to be set.")

    secret = base64.b64encode(bytes(SH_CLIENT_SECRET, "ascii")).decode("ascii").rstrip()
    r = app_client.get(
        "/credentials/basic",
        headers={
            "Authorization": "Basic " + base64.b64encode(bytes(f"{SH_CLIENT_ID}:{secret}", "ascii")).decode("ascii"),
        },
    )
    assert r.status_code == 200, r.data
    j = r.json
    return f'Bearer basic//{j["access_token"]}'


###################################


def test_root(app_client):
    """
    Test root ('/') endpoint:
      - response must contain all the required keys
      - list of endpoints must contain at least ourselves
    """
    r = app_client.get("/")

    assert r.status_code == 200
    actual = json.loads(r.data.decode("utf-8"))

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
    assert actual["backend_version"] == "6.7.8"

    # list of endpoints must contain at least ourselves:
    expected_endpoint = {
        "path": "/",
        "methods": ["GET"],
    }
    assert expected_endpoint in actual["endpoints"]


@with_mocked_auth
def test_manage_batch_jobs(app_client, example_authorization_header_with_oidc):
    """
    - test POST "/jobs"
    - test /jobs/job_id endpoints
    """

    bbox = {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2}
    # PROCESS GRAPH CURRENTLY NOT SUPPORTED
    # data = {
    #     "process": {
    #         "process_graph": {
    #             "loadco1": {
    #                 "process_id": "load_collection",
    #                 "arguments": {
    #                     "id": "S2L1C",
    #                     "spatial_extent": bbox,
    #                     "temporal_extent": ["2017-01-01", "2017-02-01"],
    #                 },
    #                 "result": True,
    #             },
    #         },
    #     },
    # }
    data = {
        "process": {
            "process_graph": {
                "loadco1": {
                    "process_id": "load_collection",
                    "arguments": {
                        "id": "sentinel-2-l1c",
                        "spatial_extent": bbox,
                        "temporal_extent": ["2019-08-16", "2019-08-18"],
                        "bands": ["B01", "B02"],
                    },
                },
                "mean1": {
                    "process_id": "reduce_dimension",
                    "arguments": {
                        "data": {"from_node": "loadco1"},
                        "dimension": "t",
                        "reducer": {
                            "process_graph": {
                                "1": {
                                    "process_id": "mean",
                                    "arguments": {"data": {"from_parameter": "data"}},
                                    "result": True,
                                }
                            }
                        },
                    },
                },
                "result1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "mean1"}, "format": "gtiff"},
                    "result": True,
                },
            }
        },
    }

    r = app_client.post(
        "/jobs", data=json.dumps(data), headers=example_authorization_header_with_oidc, content_type="application/json"
    )
    assert r.status_code == 201, r.data

    record_id = r.headers["OpenEO-Identifier"]

    r = app_client.get("/jobs/{}".format(record_id), headers=example_authorization_header_with_oidc)
    actual = json.loads(r.data.decode("utf-8"))

    assert r.status_code == 200
    assert actual["status"] == "created"
    assert actual["process"]["process_graph"] == data["process"]["process_graph"]
    assert actual["id"] == record_id

    bbox2 = {"west": 12.1, "east": 12.6, "north": 42.6, "south": 41.2}
    data2 = {
        "process": {
            "process_graph": {
                "loadco1": {
                    "process_id": "load_collection",
                    "arguments": {
                        "id": "sentinel-2-l1c",
                        "spatial_extent": bbox2,
                        "temporal_extent": ["2017-01-01", "2017-03-01"],
                        "bands": ["B01", "B02"],
                    },
                },
                "mean1": {
                    "process_id": "reduce_dimension",
                    "arguments": {
                        "data": {"from_node": "loadco1"},
                        "dimension": "t",
                        "reducer": {
                            "process_graph": {
                                "1": {
                                    "process_id": "mean",
                                    "arguments": {"data": {"from_parameter": "data"}},
                                    "result": True,
                                }
                            }
                        },
                    },
                },
                "result1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "mean1"}, "format": "gtiff"},
                    "result": True,
                },
            }
        }
        # PROCESS GRAPH CURRENTLY NOT SUPPORTED
        # {
        #     "process_graph": {
        #         "loadco1": {
        #             "process_id": "load_collection",
        #             "arguments": {
        #                 "id": "S2L1C",
        #                 "spatial_extent": bbox2,
        #                 "temporal_extent": ["2017-01-01", "2017-03-01"],
        #             },
        #             "result": True,
        #         },
        #     },
        # }
        ,
        "title": "Load collection test",
    }

    r = app_client.patch(
        "/jobs/{}".format(record_id),
        data=json.dumps(data2),
        headers=example_authorization_header_with_oidc,
        content_type="application/json",
    )

    assert r.status_code == 204, r.data

    r = app_client.get("/jobs/{}".format(record_id), headers=example_authorization_header_with_oidc)
    actual = json.loads(r.data.decode("utf-8"))

    assert r.status_code == 200
    assert actual["process"]["process_graph"] == data2["process"]["process_graph"]
    assert actual["title"] == data2["title"]

    r = app_client.delete("/jobs/{}".format(record_id), headers=example_authorization_header_with_oidc)

    assert r.status_code == 204, r.data

    r = app_client.get("/jobs/{}".format(record_id), headers=example_authorization_header_with_oidc)

    assert r.status_code == 404


@with_mocked_auth
@with_mocked_reporting
@with_mocked_batch_request_info
def test_process_batch_job(app_client, example_process_graph, example_authorization_header_with_oidc):
    """
    - test /jobs/job_id/results endpoints
    """
    data = {
        "process": {
            "process_graph": example_process_graph,
        }
    }
    r = app_client.post(
        "/jobs", data=json.dumps(data), headers=example_authorization_header_with_oidc, content_type="application/json"
    )
    assert r.status_code == 201, r.data
    job_id = r.headers["OpenEO-Identifier"]

    r = app_client.delete(f"/jobs/{job_id}/results", headers=example_authorization_header_with_oidc)
    assert r.status_code == 204, r.data

    # without authorization header, this call fails:
    r = app_client.post(f"/jobs/{job_id}/results")
    assert r.status_code == 401, r.data

    r = app_client.post(f"/jobs/{job_id}/results", headers=example_authorization_header_with_oidc)
    assert r.status_code == 202, r.data

    # it might take some time before the job is accepted - keep trying for 5s:
    for _ in range(10):
        r = app_client.get(f"/jobs/{job_id}", headers=example_authorization_header_with_oidc)
        actual = json.loads(r.data.decode("utf-8"))
        assert r.status_code == 200, r.data
        if actual["status"] != "created":
            break
        time.sleep(0.5)
    assert actual["status"] in ["queued", "running", "error", "finished"]

    r = app_client.get(f"/jobs/{job_id}/results", headers=example_authorization_header_with_oidc)
    actual = json.loads(r.data.decode("utf-8"))
    assert r.status_code == 400, r.data
    assert actual["code"] == "JobNotFinished"

    r = app_client.delete(f"/jobs/{job_id}/results", headers=example_authorization_header_with_oidc)
    assert r.status_code == 204, r.data


@with_mocked_auth
@with_mocked_reporting
def test_result_not_encoded_secret(app_client, example_process_graph, example_authorization_header_with_oidc):
    """
    - test /result endpoint
    """
    data = {
        "process": {
            "process_graph": example_process_graph,
        }
    }

    r = app_client.post("/result", data=json.dumps(data), content_type="application/json")
    assert r.status_code == 401

    r = app_client.post(
        "/result",
        data=json.dumps(data),
        content_type="application/json",
        headers=example_authorization_header_with_oidc,
    )
    assert r.status_code == 200, r.data


def test_result_base64_encoded_secret(app_client, example_process_graph, authorization_header_base64):
    """
    - test /result endpoint, but this time use a base64-encoded version of password (both should work)
    """
    data = {
        "process": {
            "process_graph": example_process_graph,
        }
    }

    r = app_client.post("/result", data=json.dumps(data), content_type="application/json")
    assert r.status_code == 401

    r = app_client.post(
        "/result",
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": authorization_header_base64},
    )
    assert r.status_code == 200


@with_mocked_auth
def test_services_crud(app_client, example_process_graph_with_variables, example_authorization_header_with_oidc):
    """
    - test /services endpoint
    """
    r = app_client.get("/services", headers=example_authorization_header_with_oidc)
    expected = []
    actual = json.loads(r.data.decode("utf-8")).get("services")
    assert r.status_code == 200, r.data
    assert actual == expected

    data = {
        "title": "MyService",
        "process": {
            "process_graph": example_process_graph_with_variables,
        },
        "type": "xyz",
    }
    r = app_client.post(
        "/services",
        data=json.dumps(data),
        content_type="application/json",
        headers=example_authorization_header_with_oidc,
    )
    assert r.status_code == 201, r.data
    service_id = r.headers["OpenEO-Identifier"]

    r = app_client.get("/services", headers=example_authorization_header_with_oidc)
    assert r.status_code == 200
    services = json.loads(r.data.decode("utf-8")).get("services")
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
        "configuration": {},
    }
    assert services[0] == expected

    patch_data = {
        "title": "MyService2",
    }
    r = app_client.patch(
        "/services/{}".format(service_id),
        data=json.dumps(patch_data),
        content_type="application/json",
        headers=example_authorization_header_with_oidc,
    )
    assert r.status_code == 204

    expected.update(patch_data)

    r = app_client.get("/services", headers=example_authorization_header_with_oidc)
    assert r.status_code == 200
    services = json.loads(r.data.decode("utf-8")).get("services")
    assert len(services) == 1
    assert services[0] == expected

    r = app_client.get("/services/{}".format(service_id), headers=example_authorization_header_with_oidc)
    assert r.status_code == 200
    actual = json.loads(r.data.decode("utf-8"))
    # get record supports additional fields:
    expected.update(
        {
            "process": {
                "process_graph": example_process_graph_with_variables,
            },
            "attributes": {},
            "created": actual["created"],
        }
    )
    assert actual == expected

    # delete service and make sure it is deleted:
    r = app_client.delete("/services/{}".format(service_id), headers=example_authorization_header_with_oidc)
    assert r.status_code == 204

    r = app_client.get("/services/{}".format(service_id), headers=example_authorization_header_with_oidc)
    assert r.status_code == 404

    r = app_client.get("/services", headers=example_authorization_header_with_oidc)
    expected = []
    actual = json.loads(r.data.decode("utf-8")).get("services")
    assert r.status_code == 200
    assert actual == expected


@pytest.mark.skip(
    "Without width/height (just resx/y) the dimensions are not 100% the same as with OGC services. We should still try to fix it better."
)
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
                        "id": "sentinel-2-l1c",
                        "spatial_extent": {"west": 12.32271, "east": 12.33572, "north": 42.07112, "south": 42.06347},
                        "temporal_extent": ["2019-08-16", "2019-08-25"],
                    },
                },
                "reduce1": {
                    "process_id": "reduce_dimension",
                    "arguments": {
                        "data": {"from_node": "loadco1"},
                        "dimension": "t",
                        "reducer": {
                            "process_graph": {
                                "min": {
                                    "process_id": "min",
                                    "arguments": {"data": {"from_parameter": "data"}},
                                },
                                "mean": {
                                    "process_id": "mean",
                                    "arguments": {"data": {"from_parameter": "data"}},
                                },
                                "sum": {
                                    "process_id": "sum",
                                    "arguments": {"data": [{"from_node": "min"}, {"from_node": "mean"}]},
                                    "result": True,
                                },
                            }
                        },
                    },
                },
                "result1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "reduce1"}, "format": "gtiff"},
                    "result": True,
                },
            }
        }
    }

    r = app_client.post("/result", data=json.dumps(data), content_type="application/json")
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
    r = app_client.get("/service/xyz/{}/{}/{}/{}".format(service_id, int(zoom), int(tx), int(ty)))
    assert r.status_code == 200
    expected_data = get_expected_data("tile256x256.tiff")
    assert r.data == expected_data


# @responses.activate
@with_mocked_auth
@with_mocked_reporting
@pytest.mark.parametrize(
    "tile_size",
    [None, 256, 512],
)
def test_xyz_service_2(app_client, service_factory, get_expected_data, authorization_header, tile_size):
    process_graph = {
        "loadco1": {
            "process_id": "load_collection",
            "arguments": {
                "id": "sentinel-2-l1c",
                "spatial_extent": {
                    "west": {"from_parameter": "spatial_extent_west"},
                    "east": {"from_parameter": "spatial_extent_east"},
                    "north": {"from_parameter": "spatial_extent_north"},
                    "south": {"from_parameter": "spatial_extent_south"},
                },
                "temporal_extent": ["2019-08-01", "2019-08-18"],
                "bands": ["B01", "B02", "B03"],
            },
        },
        "reduce1": {
            "process_id": "reduce_dimension",
            "arguments": {
                "data": {"from_node": "loadco1"},
                "reducer": {
                    "process_graph": {
                        "2": {"process_id": "mean", "arguments": {"data": {"from_parameter": "data"}}, "result": True}
                    }
                },
                "dimension": "t",
            },
        },
        "linear1": {
            "process_id": "apply",
            "arguments": {
                "data": {"from_node": "reduce1"},
                "process": {
                    "process_graph": {
                        "lsr": {
                            "process_id": "linear_scale_range",
                            "arguments": {"x": {"from_parameter": "x"}, "inputMin": 0, "inputMax": 1, "outputMax": 255},
                            "result": True,
                        },
                    }
                },
            },
        },
        "result1": {
            "process_id": "save_result",
            "arguments": {"data": {"from_node": "linear1"}, "format": "jpeg"},
            "result": True,
        },
    }

    service_id = service_factory(process_graph, title="Test XYZ service", service_type="xyz", tile_size=tile_size)

    zoom, tx, ty = 14, 8660, 5908

    # AUTHENTICATION CURRENTLY NOT IMPLEMENTED
    # r = app_client.get(f"/service/xyz/{service_id}/{int(zoom)}/{int(tx)}/{int(ty)}")
    # assert r.status_code == 401, r.data

    responses.add(responses.POST, re.compile(".*"), headers={"x-processingunits-spent": "1"})

    r = app_client.get(
        f"/service/xyz/{service_id}/{int(zoom)}/{int(tx)}/{int(ty)}", headers={"Authorization": authorization_header}
    )
    assert r.status_code == 200, r.data
    # NDVI process currently not implemented.
    # expected_data = get_expected_data("tile256x256ndvi.jpeg")
    # assert r.data == expected_data, "File is not the same!"

    payload = json.loads(responses.calls[len(responses.calls) - 1].request.body)
    assert payload["output"]["width"] == tile_size if tile_size is not None else 256
    assert payload["output"]["height"] == tile_size if tile_size is not None else 256


@pytest.mark.skip("Synchronous job endpoint does not support the testing process graphs currently.")
@pytest.mark.parametrize(
    "value,double_value,expected_status_code",
    [
        (0.5, 1.0, 200),
        (0.5, 2.0, 400),
    ],
)
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
                        [[0.15, None]],
                    ]
                ],
                "dims": ["y", "x", "t", "band"],
                "coords": {
                    "y": [12.3],
                    "x": [45.1, 45.2],
                    "t": ["2019-08-01 11:00:12"],
                    "band": [["nir", None, 0.85], ["red", None, 0.66]],
                },
            },
        },
        "linear1": {
            "process_id": "apply",
            "arguments": {
                "data": {"from_node": "gencol1"},
                "process": {
                    "process_graph": {
                        "lsr": {
                            "process_id": "linear_scale_range",
                            "arguments": {
                                "x": {"from_parameter": "x"},
                                "inputMin": 0.0,
                                "inputMax": 1.0,
                                "outputMin": 0.0,
                                "outputMax": 2.0,
                            },
                            "result": True,
                        },
                    }
                },
            },
        },
        "expectedlinear1": {
            "process_id": "create_cube",
            "arguments": {
                "data": [
                    [
                        [
                            [double_value, 0.3],
                        ],
                        [[0.3, None]],
                    ]
                ],
                "dims": ["y", "x", "t", "band"],
                "coords": {
                    "y": [12.3],
                    "x": [45.1, 45.2],
                    "t": ["2019-08-01 11:00:12"],
                    "band": [["nir", None, 0.85], ["red", None, 0.66]],
                },
            },
        },
        "assertlinear1": {
            "process_id": "assert_equals",
            "arguments": {"a": {"from_node": "linear1"}, "b": {"from_node": "expectedlinear1"}},
        },
        "result1": {
            "process_id": "save_result",
            "arguments": {"data": {"from_node": "linear1"}, "format": "gtiff", "options": {"datatype": "float32"}},
            "result": True,
        },
    }

    data = {
        "process": {
            "process_graph": process_graph,
        }
    }
    r = app_client.post(
        "/result",
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": authorization_header},
    )
    assert r.status_code == expected_status_code, r.data


def _get_test_process_graphs_filenames():
    for f in glob.glob(os.path.join(os.path.dirname(__file__), "test_process_graphs/*.json")):
        if not os.path.isfile(f) or os.path.basename(f).startswith("_"):
            print("Skipping: {}".format(os.path.basename(f)))
            continue
        yield f


@pytest.mark.skip("Synchronous job endpoint does not support the testing process graphs currently.")
@pytest.mark.parametrize("process_graph_filename", _get_test_process_graphs_filenames())
def test_run_test_process_graphs(app_client, process_graph_filename, authorization_header):
    """
    Load process graph definitions from test_process_graph/*.json and execute them
    via POST /result/, expecting status 200 on each of them.
    """
    with open(process_graph_filename, "rt") as f:
        process_graph_json = f.read()
    process_graph = json.loads(process_graph_json)
    data = {
        "process": {
            "process_graph": process_graph,
        }
    }
    r = app_client.post(
        "/result",
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": authorization_header},
    )
    assert r.status_code == 200, r.data


@with_mocked_auth
def test_process_graph_api(
    app_client, example_process_graph, fahrenheit_to_celsius_process, example_authorization_header_with_oidc
):
    """
    Get /process_graphs/ (must be empty), test CRUD operations.
    """
    # get a list of process graphs, should be empty:
    r = app_client.get("/process_graphs", headers=example_authorization_header_with_oidc)
    assert r.status_code == 200, r.data
    expected = []
    actual = json.loads(r.data.decode("utf-8")).get("processes")
    assert actual == expected

    # Use invalid process graph id:
    process_graph_id = "c91ea247-2ec0-4048-ab6c-1c31c3ecfa7e"
    data = {
        "summary": "invalid id",
        "process_graph": example_process_graph,
    }
    r = app_client.put(
        f"/process_graphs/{process_graph_id}",
        data=json.dumps(data),
        headers=example_authorization_header_with_oidc,
        content_type="application/json",
    )
    assert r.status_code == 400, r.data

    # create a process graph:
    process_graph_id = "testing_process_graph"
    data = {"summary": "test", "process_graph": example_process_graph, "experimental": False, "deprecated": True}
    r = app_client.put(
        f"/process_graphs/{process_graph_id}",
        data=json.dumps(data),
        headers=example_authorization_header_with_oidc,
        content_type="application/json",
    )
    assert r.status_code == 200, r.data

    # get a list of process graphs again:
    r = app_client.get("/process_graphs", headers=example_authorization_header_with_oidc)
    assert r.status_code == 200, r.data
    expected = [
        {"id": process_graph_id, "summary": "test", "experimental": False, "deprecated": True},
    ]
    actual = json.loads(r.data.decode("utf-8")).get("processes")
    assert actual == expected

    # get the process graph:
    r = app_client.get("/process_graphs/{}".format(process_graph_id), headers=example_authorization_header_with_oidc)
    assert r.status_code == 200, r.data
    expected = {
        "summary": "test",
        "description": None,
        "parameters": None,
        "returns": None,
        "id": process_graph_id,
        "categories": [],
        "deprecated": True,
        "experimental": False,
        "exceptions": {},
        "examples": [],
        "links": [],
        "process_graph": example_process_graph,
    }
    actual = json.loads(r.data.decode("utf-8"))
    assert actual == expected

    # change it:
    data = {
        "summary": "test2",
        "description": "asdf",
        "process_graph": example_process_graph,
    }
    r = app_client.put(
        "/process_graphs/{}".format(process_graph_id),
        data=json.dumps(data),
        headers=example_authorization_header_with_oidc,
        content_type="application/json",
    )
    assert r.status_code == 200, r.data

    # get the process graph again:
    r = app_client.get("/process_graphs/{}".format(process_graph_id), headers=example_authorization_header_with_oidc)
    assert r.status_code == 200, r.data
    expected = {
        "id": process_graph_id,
        "summary": "test2",
        "description": "asdf",
        "parameters": None,
        "returns": None,
        "categories": [],
        "deprecated": False,
        "experimental": False,
        "exceptions": {},
        "examples": [],
        "links": [],
        "process_graph": example_process_graph,
    }
    actual = json.loads(r.data.decode("utf-8"))
    assert actual == expected

    # delete it:
    r = app_client.delete("/process_graphs/{}".format(process_graph_id), headers=example_authorization_header_with_oidc)
    assert r.status_code == 204, r.data

    # make sure the record is removed:
    r = app_client.get("/process_graphs/{}".format(process_graph_id), headers=example_authorization_header_with_oidc)
    assert r.status_code == 404
    r = app_client.get("/process_graphs", headers=example_authorization_header_with_oidc)
    assert r.status_code == 200, r.data
    expected = []
    actual = json.loads(r.data.decode("utf-8")).get("processes")
    assert actual == expected

    # create a process graph with invalid id (clashes with pre-defined process):
    process_graph_id = "reduce_dimension"
    data = {
        "summary": "Invalid process",
        "process_graph": example_process_graph,
    }
    r = app_client.put(
        f"/process_graphs/{process_graph_id}",
        data=json.dumps(data),
        headers=example_authorization_header_with_oidc,
        content_type="application/json",
    )
    assert r.status_code == 400, r.data

    # create a process graph with with id different in payload than url param:
    process_graph_id = "id_in_url"
    data = {
        "id": "id_in_payload",
        "summary": "Id in payload different than url param",
        "process_graph": example_process_graph,
    }
    r = app_client.put(
        f"/process_graphs/{process_graph_id}",
        data=json.dumps(data),
        headers=example_authorization_header_with_oidc,
        content_type="application/json",
    )
    assert r.status_code == 200, r.data
    # Check the id in payload got overridden
    r = app_client.get("/process_graphs/{}".format(process_graph_id), headers=example_authorization_header_with_oidc)
    assert r.status_code == 200, r.data
    assert json.loads(r.data.decode("utf-8"))["id"] == process_graph_id

    # Save a user-defined process
    process_graph_id = "fahrenheit_to_celsius"
    process_graph, parameters = fahrenheit_to_celsius_process
    data = {
        "summary": "Convert fahrenheit_to_celsius",
        "process_graph": process_graph,
        "parameters": parameters,
    }
    r = app_client.put(
        f"/process_graphs/{process_graph_id}",
        data=json.dumps(data),
        headers=example_authorization_header_with_oidc,
        content_type="application/json",
    )
    assert r.status_code == 200, r.data

    # Save a user-defined process without known parameters
    process_graph_id = "fahrenheit_to_celsius"
    data = {
        "summary": "Convert fahrenheit_to_celsius",
        "process_graph": process_graph,
        "parameters": None,
    }
    r = app_client.put(
        f"/process_graphs/{process_graph_id}",
        data=json.dumps(data),
        headers=example_authorization_header_with_oidc,
        content_type="application/json",
    )
    assert r.status_code == 200, r.data

    # Try to save a user-defined process explicitly stating there are no parameters
    # " Specifying an empty array is different from (if allowed) null or the property being absent. An empty array means the process has no parameters."
    process_graph_id = "fahrenheit_to_celsius"
    data = {
        "summary": "Convert fahrenheit_to_celsius",
        "process_graph": process_graph,
        "parameters": [],
    }
    r = app_client.put(
        f"/process_graphs/{process_graph_id}",
        data=json.dumps(data),
        headers=example_authorization_header_with_oidc,
        content_type="application/json",
    )
    assert r.status_code == 400, r.data


@pytest.mark.skip("JSON output format currently not supported.")
def test_batch_job_json_output(app_client, authorization_header):
    """
    - test /jobs/job_id/results endpoints
    """
    data = {
        "process": {
            "process_graph": {
                "gencol1": {
                    "process_id": "create_cube",
                    "arguments": {
                        "data": [[[[0.25, 0.15], [0.15, 0.25]], [[-np.inf, np.inf], [None, None]]]],
                        "dims": ["y", "x", "t", "band"],
                        "coords": {
                            "y": [12.3],
                            "x": [45.1, 45.2],
                            "t": ["2019-08-01 11:00:12", "2019-08-02 13:00:12"],
                            "band": [["nir", None, 0.85], ["red", None, 0.66]],
                        },
                    },
                },
                "result1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "gencol1"}, "format": "json"},
                    "result": True,
                },
            },
        }
    }
    r = app_client.post("/jobs", data=json.dumps(data), content_type="application/json")
    assert r.status_code == 201
    job_id = r.headers["OpenEO-Identifier"]

    r = app_client.post(f"/jobs/{job_id}/results", headers={"Authorization": authorization_header})
    assert r.status_code == 202

    # it might take some time before the job is accepted and done - keep trying for 5s:
    for _ in range(10):
        r = app_client.get(f"/jobs/{job_id}")
        actual = json.loads(r.data.decode("utf-8"))
        assert r.status_code == 200
        if actual["status"] not in ["created", "queued", "running"]:
            break
        time.sleep(0.5)
    assert actual["status"] == "finished"

    r = app_client.get(f"/jobs/{job_id}/results")
    actual = json.loads(r.data.decode("utf-8"))
    assert r.status_code == 200

    asset_url = actual["assets"]["result.json"]["href"]
    r = requests.get(asset_url)
    r.raise_for_status()
    result = r.json()

    expected_result = {
        "dims": ["y", "x", "t", "band"],
        "attrs": {"bbox": {"xmin": 12.0, "ymin": 45.0, "xmax": 13.0, "ymax": 46.0, "crs": "EPSG:4326"}},
        "data": [[[[0.25, 0.15], [0.15, 0.25]], [[None, None], [None, None]]]],
        "coords": {
            "y": {"dims": ["y"], "attrs": {}, "data": [12.3]},
            "x": {"dims": ["x"], "attrs": {}, "data": [45.1, 45.2]},
            "t": {"dims": ["t"], "attrs": {}, "data": ["2019-08-01T11-00-12", "2019-08-02T13-00-12"]},
            "band": {
                "dims": ["band"],
                "attrs": {},
                "data": [
                    {"name": "nir", "alias": None, "wavelength": 0.85},
                    {"name": "red", "alias": None, "wavelength": 0.66},
                ],
            },
        },
        "name": None,
    }
    assert result == expected_result


def test_collections(app_client):
    mocked_collections = load_collections_fixtures("fixtures/collection_information/", "sentinel-2-l1c")
    collections.set_collections(mocked_collections)

    # get a list of all collections:
    r = app_client.get("/collections")
    assert r.status_code == 200, r.data
    actual = json.loads(r.data.decode("utf-8"))
    assert len(actual["collections"]) == 1

    # use valid collection id:
    collection_id = "sentinel-2-l1c"
    r = app_client.get(f"/collections/{collection_id}")
    assert r.status_code == 200, r.data
    expected = mocked_collections[collection_id]
    actual = json.loads(r.data.decode("utf-8"))
    assert actual == expected

    # Use invalid collection id:
    collection_id = "invalid_collection_id"
    r = app_client.get(f"/collections/{collection_id}")
    assert r.status_code == 404, r.data
    expected = "CollectionNotFound"
    actual = json.loads(r.data.decode("utf-8")).get("code")
    assert actual == expected


def test_sentinel2_l1c_collections_aliases(app_client):
    mocked_collections = load_collections_fixtures("fixtures/collection_information/", "SENTINEL2_L1C*")
    collections.set_collections(mocked_collections)

    # get a list of all SENTINEL2_L1C collections:
    r = app_client.get("/collections")
    assert r.status_code == 200, r.data
    actual = json.loads(r.data.decode("utf-8"))
    assert len(actual["collections"]) == 2

    # use SENTINEL2_L1C_SENTINELHUB collection id:
    collection_id = "SENTINEL2_L1C_SENTINELHUB"
    r = app_client.get(f"/collections/{collection_id}")
    assert r.status_code == 200, r.data
    expected_S2L1C_SH = mocked_collections[collection_id]
    actual_S2L1C_SH = json.loads(r.data.decode("utf-8"))
    assert actual_S2L1C_SH == expected_S2L1C_SH

    # use SENTINEL2_L1C alias:
    collection_id = "SENTINEL2_L1C"
    r = app_client.get(f"/collections/{collection_id}")
    assert r.status_code == 200, r.data
    expected_S2L1C = mocked_collections[collection_id]
    actual_S2L1C = json.loads(r.data.decode("utf-8"))
    assert actual_S2L1C == expected_S2L1C

    # check contents of both collections (except id)
    for key in actual_S2L1C_SH:
        if key != "id":
            assert actual_S2L1C_SH[key] == actual_S2L1C[key]


def test_sentinel2_l2a_collections_aliases(app_client):
    mocked_collections = load_collections_fixtures("fixtures/collection_information/", "SENTINEL2_L2A*")
    collections.set_collections(mocked_collections)

    # get a list of all SENTINEL2_L2A collections:
    r = app_client.get("/collections")
    assert r.status_code == 200, r.data
    actual = json.loads(r.data.decode("utf-8"))
    assert len(actual["collections"]) == 2

    # use SENTINEL2_L2A_SENTINELHUB collection id:
    collection_id = "SENTINEL2_L2A_SENTINELHUB"
    r = app_client.get(f"/collections/{collection_id}")
    assert r.status_code == 200, r.data
    expected_S2L2A_SH = mocked_collections[collection_id]
    actual_S2L2A_SH = json.loads(r.data.decode("utf-8"))
    assert actual_S2L2A_SH == expected_S2L2A_SH

    # use SENTINEL2_L2A alias:
    collection_id = "SENTINEL2_L2A"
    r = app_client.get(f"/collections/{collection_id}")
    assert r.status_code == 200, r.data
    expected_S2L2A = mocked_collections[collection_id]
    actual_S2L2A = json.loads(r.data.decode("utf-8"))
    assert actual_S2L2A == expected_S2L2A

    # check contents of both collections (except id)
    for key in actual_S2L2A_SH:
        if key != "id":
            assert actual_S2L2A_SH[key] == actual_S2L2A[key]


@responses.activate
@pytest.mark.parametrize(
    "collection_id,collection_type,request_url",
    [
        ("landsat-7-etm+-l2", "landsat-etm-l2", "https://services-uswest2.sentinel-hub.com"),
        ("corine-land-cover", "byoc-cbdba844-f86d-41dc-95ad-b3f7f12535e9", "https://creodias.sentinel-hub.com"),
        ("sentinel-2-l1c", "sentinel-2-l1c", "https://services.sentinel-hub.com"),
    ],
)
def test_fetching_correct_collection_type(app_client, collection_id, collection_type, request_url):
    process_graph = {
        "loadco1": {
            "process_id": "load_collection",
            "arguments": {
                "id": collection_id,
                "spatial_extent": {"west": 12.32271, "east": 12.33572, "north": 42.07112, "south": 42.06347},
                "temporal_extent": ["2019-08-16", "2019-08-18"],
                "bands": collections.get_collection(collection_id)["cube:dimensions"]["bands"]["values"],
            },
        },
        "mean1": {
            "process_id": "reduce_dimension",
            "arguments": {
                "data": {"from_node": "loadco1"},
                "dimension": "t",
                "reducer": {
                    "process_graph": {
                        "1": {"process_id": "mean", "arguments": {"data": {"from_parameter": "data"}}, "result": True}
                    }
                },
            },
        },
        "result1": {
            "process_id": "save_result",
            "arguments": {"data": {"from_node": "mean1"}, "format": "gtiff"},
            "result": True,
        },
    }

    r = app_client.post(
        "/result",
        data=json.dumps({"process": {"process_graph": process_graph}}),
        content_type="application/json",
    )
    if len(responses.calls) == 2:
        assert responses.calls[1].request.url == f"{request_url}/api/v1/process"
        assert json.loads(responses.calls[1].request.body)["input"]["data"][0]["type"] == collection_type
    if len(responses.calls) == 1:
        assert responses.calls[0].request.url == f"{request_url}/api/v1/process"
        assert json.loads(responses.calls[0].request.body)["input"]["data"][0]["type"] == collection_type


@with_mocked_auth
@with_mocked_reporting
@pytest.mark.parametrize(
    "collection_id,bands,should_raise_error",
    [
        ("landsat-7-etm+-l2", ["B01", "B02", "B03"], False),
        ("landsat-7-etm+-l2", ["B01", "Non-existent band", "B03"], True),
        ("corine-land-cover", ["CLC"], False),
        ("corine-land-cover", ["Non-existent band"], True),
        ("corine-land-cover", None, False),
        (
            "sentinel-2-l1c",
            [
                "B01",
                "B02",
                "B03",
                "B04",
                "B05",
                "B06",
                "B07",
                "B08",
                "B8A",
                "B09",
                "B10",
                "B11",
                "B12",
                "CLP",
                "CLM",
                "sunAzimuthAngles",
                "sunZenithAngles",
                "viewAzimuthMean",
                "viewZenithMean",
                "dataMask",
                "Non-existent band",
            ],
            True,
        ),
    ],
)
def test_validate_bands(
    app_client,
    get_example_process_graph_with_bands_and_collection,
    collection_id,
    bands,
    should_raise_error,
    example_authorization_header_with_oidc,
):
    process_graph = get_example_process_graph_with_bands_and_collection(bands, collection_id)
    payload = json.dumps({"process": {"process_graph": process_graph}})

    r = app_client.post(
        "/result",
        data=payload,
        headers=example_authorization_header_with_oidc,
        content_type="application/json",
    )

    if should_raise_error:
        response_data = json.loads(r.data.decode("utf-8"))
        assert r.status_code == 400, r.data
        assert (
            f"Invalid process graph: 'non-existent band' is not a valid band name for collection '{collection_id}'"
            in response_data["message"]
        )
    else:
        assert r.status_code == 200, r.data

    r = app_client.post(
        "/jobs", data=payload, headers=example_authorization_header_with_oidc, content_type="application/json"
    )

    if should_raise_error:
        response_data = json.loads(r.data.decode("utf-8"))
        assert r.status_code == 400, r.data
        assert (
            f"Invalid process graph: 'non-existent band' is not a valid band name for collection '{collection_id}'"
            in response_data["message"]
        )
    else:
        assert r.status_code == 201, r.data


@with_mocked_auth
@pytest.mark.parametrize(
    "bands,collection_id,spatial_extent,file_format,options,backend_estimate,expected_costs,n_tiles,tile_width,tile_height,expected_file_size",
    [
        (
            ["B01"],
            "sentinel-2-l1c",
            {"west": 12.32271, "east": 12.33572, "north": 42.07112, "south": 42.06347},
            "gtiff",
            None,
            30,
            12,
            2,
            2004,
            2004,
            2 * 2004 * 2004 * 8 * 4,  # n_tiles * tile_width * tile_height * n_output_bands * n_bytes
        ),
        (
            ["B03"],
            "sentinel-2-l1c",
            {"west": 12.32271, "east": 12.33572, "north": 42.07112, "south": 42.06347},
            "gtiff",
            None,
            30,
            12,
            1,
            2004,
            2004,
            1 * 2004 * 2004 * 8 * 4,
        ),
        (
            ["B01"],
            "sentinel-2-l1c",
            {"west": 12.32271, "east": 12.33572, "north": 42.07112, "south": 42.06347},
            "gtiff",
            {"datatype": "uint16"},
            30,
            12,
            2,
            2004,
            2004,
            2 * 2004 * 2004 * 8 * 2,
        ),
    ],
)
def test_batch_job_estimate(
    app_client,
    get_process_graph,
    example_authorization_header_with_oidc,
    bands,
    collection_id,
    spatial_extent,
    file_format,
    options,
    backend_estimate,
    expected_costs,
    n_tiles,
    tile_width,
    tile_height,
    expected_file_size,
):
    responses.add(
        responses.POST,
        re.compile("https://(services|creodias)(-uswest2)?.sentinel-hub.com/api/v1/batch/process"),
        body=json.dumps({"id": "example", "processRequest": {}, "status": "CREATED", "tileCount": n_tiles}),
    )
    responses.add(
        responses.GET,
        re.compile("https://(services|creodias)(-uswest2)?.sentinel-hub.com/api/v1/batch/tilinggrids"),
        body=json.dumps(tilinggrids_response),
    )
    responses.add(
        responses.POST,
        re.compile("https://(services|creodias)(-uswest2)?.sentinel-hub.com/api/v1/batch/process/example/analyse"),
    )
    responses.add(
        responses.GET,
        re.compile("https://(services|creodias)(-uswest2)?.sentinel-hub.com/api/v1/batch/process/example"),
        body=json.dumps(
            {
                "valueEstimate": backend_estimate,
                "id": "example",
                "processRequest": {},
                "status": "ANALYSIS_DONE",
                "tileCount": n_tiles,
                "tileWidthPx": tile_width,
                "tileHeightPx": tile_height,
            }
        ),
    )

    data = {
        "process": {
            "process_graph": get_process_graph(
                bands=bands,
                collection_id=collection_id,
                spatial_extent=spatial_extent,
                file_format=file_format,
                options=options,
            ),
        }
    }

    r = app_client.post(
        "/jobs", data=json.dumps(data), headers=example_authorization_header_with_oidc, content_type="application/json"
    )
    assert r.status_code == 201, r.data
    job_id = r.headers["OpenEO-Identifier"]

    r = app_client.get(f"/jobs/{job_id}/estimate")
    assert r.status_code == 401, r.data

    r = app_client.get(f"/jobs/{job_id}/estimate", headers=example_authorization_header_with_oidc)
    assert r.status_code == 200, r.data
    data = json.loads(r.data.decode("utf-8"))
    assert data["costs"] == expected_costs
    assert data["size"] == expected_file_size


@responses.activate
def test_user_workspace(app_client, example_authorization_header_with_oidc, example_process_graph):
    """
    Test jobs, services and process graphs are only available to the user who created them
    """
    data = {
        "process": {
            "process_graph": example_process_graph,
        }
    }
    current_user_index = 0
    user_ids = ["example-id1", "example-id-2"]

    def request_callback(request):
        resp_body = {
            "sub": user_ids[current_user_index],
            "eduperson_entitlement": [
                "urn:mace:egi.eu:group:vo.openeo.cloud:role=vm_operator#aai.egi.eu",
                "urn:mace:egi.eu:group:vo.openeo.cloud:role=member#aai.egi.eu",
                "urn:mace:egi.eu:group:vo.openeo.cloud:role=early_adopter#aai.egi.eu",
            ],
        }
        return (200, {}, json.dumps(resp_body))

    responses.add(
        responses.GET,
        "https://aai.egi.eu/auth/realms/egi/.well-known/openid-configuration",
        json={"userinfo_endpoint": "http://dummy_userinfo_endpoint"},
    )
    responses.add_callback(responses.GET, "http://dummy_userinfo_endpoint", callback=request_callback)
    responses.add_passthru(re.compile(".*"))

    # Create a batch job for user 0
    current_user_index = 0
    r = app_client.post(
        "/jobs", data=json.dumps(data), headers=example_authorization_header_with_oidc, content_type="application/json"
    )
    assert r.status_code == 201, r.data
    record_id_1 = r.headers["OpenEO-Identifier"]
    # Fetch the batch job with user 0
    r = app_client.get("/jobs/{}".format(record_id_1), headers=example_authorization_header_with_oidc)
    actual = json.loads(r.data.decode("utf-8"))
    assert r.status_code == 200
    assert actual["id"] == record_id_1
    # Fetch the batch job with user 1
    current_user_index = 1
    r = app_client.get("/jobs/{}".format(record_id_1), headers=example_authorization_header_with_oidc)
    assert r.status_code == 404
    # Fetch all jobs as user 1
    r = app_client.get("/jobs", headers=example_authorization_header_with_oidc)
    actual = json.loads(r.data.decode("utf-8"))
    assert actual["jobs"] == []
    # Fetch all jobs as user 0
    current_user_index = 0
    r = app_client.get("/jobs", headers=example_authorization_header_with_oidc)
    actual = json.loads(r.data.decode("utf-8"))
    assert len(actual["jobs"]) == 1
    assert actual["jobs"][0]["id"] == record_id_1
    # Create a batch job for user 1
    current_user_index = 1
    r = app_client.post(
        "/jobs", data=json.dumps(data), headers=example_authorization_header_with_oidc, content_type="application/json"
    )
    record_id_2 = r.headers["OpenEO-Identifier"]
    assert r.status_code == 201, r.data
    # Fetch all jobs as user 1
    r = app_client.get("/jobs", headers=example_authorization_header_with_oidc)
    actual = json.loads(r.data.decode("utf-8"))
    assert len(actual["jobs"]) == 1
    assert actual["jobs"][0]["id"] == record_id_2

    # Create a service for user 0
    data = {
        "title": "Example service",
        "process": {
            "process_graph": example_process_graph,
        },
        "type": "xyz",
    }
    current_user_index = 0
    r = app_client.post(
        "/services",
        data=json.dumps(data),
        headers=example_authorization_header_with_oidc,
        content_type="application/json",
    )
    assert r.status_code == 201, r.data
    record_id_1 = r.headers["OpenEO-Identifier"]
    # Fetch the batch job with user 0
    r = app_client.get("/services/{}".format(record_id_1), headers=example_authorization_header_with_oidc)
    actual = json.loads(r.data.decode("utf-8"))
    assert r.status_code == 200
    assert actual["id"] == record_id_1
    # Fetch the batch job with user 1
    current_user_index = 1
    r = app_client.get("/services/{}".format(record_id_1), headers=example_authorization_header_with_oidc)
    assert r.status_code == 404
    # Fetch all jobs as user 1
    r = app_client.get("/services", headers=example_authorization_header_with_oidc)
    actual = json.loads(r.data.decode("utf-8"))
    assert actual["services"] == []
    # Fetch all jobs as user 0
    current_user_index = 0
    r = app_client.get("/services", headers=example_authorization_header_with_oidc)
    actual = json.loads(r.data.decode("utf-8"))
    assert len(actual["services"]) == 1
    assert actual["services"][0]["id"] == record_id_1
    # Create a batch job for user 1
    current_user_index = 1
    r = app_client.post(
        "/services",
        data=json.dumps(data),
        headers=example_authorization_header_with_oidc,
        content_type="application/json",
    )
    record_id_2 = r.headers["OpenEO-Identifier"]
    assert r.status_code == 201, r.data
    # Fetch all jobs as user 1
    r = app_client.get("/services", headers=example_authorization_header_with_oidc)
    actual = json.loads(r.data.decode("utf-8"))
    assert len(actual["services"]) == 1
    assert actual["services"][0]["id"] == record_id_2

    # Create a process graph for user 0
    process_graph_id = "testing_process_graph"
    data = {
        "summary": "test",
        "process_graph": example_process_graph,
    }
    current_user_index = 0
    r = app_client.put(
        f"/process_graphs/{process_graph_id}",
        data=json.dumps(data),
        headers=example_authorization_header_with_oidc,
        content_type="application/json",
    )
    assert r.status_code == 200, r.data
    # Fetch all process graphs as user 1
    current_user_index = 1
    r = app_client.get("/process_graphs", headers=example_authorization_header_with_oidc)
    actual = json.loads(r.data.decode("utf-8"))
    assert actual["processes"] == []
    # Fetch all process graphs as user 0
    current_user_index = 0
    r = app_client.get("/process_graphs", headers=example_authorization_header_with_oidc)
    actual = json.loads(r.data.decode("utf-8"))
    assert len(actual["processes"]) == 1
    assert actual["processes"][0]["id"] == process_graph_id


@with_mocked_auth
@pytest.mark.parametrize(
    "spatial_extent,temporal_extent",
    [
        ({"west": 1.32271, "east": 12.33572, "north": 42.07112, "south": 2.06347}, ["2019-08-16", "2019-08-18"]),
    ],
)
def test_sync_jobs_filesize(
    app_client, example_process_graph, example_authorization_header_with_oidc, spatial_extent, temporal_extent
):
    """
    - Test requests with too large file size are rejected
    """
    example_process_graph["loadco1"]["arguments"]["spatial_extent"] = spatial_extent
    example_process_graph["loadco1"]["arguments"]["temporal_extent"] = temporal_extent
    data = {
        "process": {
            "process_graph": example_process_graph,
        }
    }

    r = app_client.post(
        "/result",
        data=json.dumps(data),
        headers=example_authorization_header_with_oidc,
        content_type="application/json",
    )
    assert r.status_code == ProcessGraphComplexity.http_code, r.data
    assert ProcessGraphComplexity.error_code in r.data.decode("utf-8")


def test_user_token_user(app_client, example_process_graph):
    """
    - Test user token is used in request
    """
    responses.add(
        responses.POST,
        "https://services.sentinel-hub.com/api/v1/process",
        match=[matchers.header_matcher({"Authorization": f"Bearer {valid_sh_token}"})],
    )
    responses.add(
        responses.POST,
        "https://services.sentinel-hub.com/api/v1/batch/process",
        json={"id": "example", "processRequest": {}, "status": "CREATED"},
        match=[matchers.header_matcher({"Authorization": f"Bearer {valid_sh_token}"})],
    )

    data = {
        "process": {
            "process_graph": example_process_graph,
        }
    }
    headers = {"Authorization": f"Bearer basic//{valid_sh_token}"}

    r = app_client.post(
        "/result",
        data=json.dumps(data),
        headers=headers,
        content_type="application/json",
    )
    assert r.status_code == 200, r.data
    r = app_client.post("/jobs", data=json.dumps(data), headers=headers, content_type="application/json")
    assert r.status_code == 201, r.data


def test_job_with_deleted_batch_request(app_client, example_process_graph):
    data = {
        "process": {
            "process_graph": example_process_graph,
        }
    }
    headers = {"Authorization": f"Bearer basic//{valid_sh_token}"}

    r = app_client.post(
        "/jobs",
        data=json.dumps(data),
        headers=headers,
        content_type="application/json",
    )
    assert r.status_code == 201, r.data

    record_id = r.headers["OpenEO-Identifier"]

    job_data = JobsPersistence.get_by_id(record_id)
    batch_request_id = job_data["batch_request_id"]
    user = SHUser(sh_access_token=valid_sh_token)
    sentinel_hub = SentinelHub(user=user)
    sentinel_hub.delete_batch_job(batch_request_id)

    r = app_client.get("/jobs", headers=headers)
    actual = json.loads(r.data.decode("utf-8"))
    assert r.status_code == 200, r.data
    assert len(actual["jobs"]) == 1
    assert actual["jobs"][0]["id"] == record_id
    assert actual["jobs"][0]["status"] == "finished"

    r = app_client.patch(
        "/jobs/{}".format(record_id),
        data=json.dumps({"description": "some description"}),
        headers=headers,
        content_type="application/json",
    )
    assert r.status_code == 204, r.data

    r = app_client.get("/jobs/{}".format(record_id), headers=headers)
    actual = json.loads(r.data.decode("utf-8"))

    assert r.status_code == 200, r.data
    assert actual["status"] == "finished"
    assert actual["description"] == "some description"

    r = app_client.get(f"/jobs/{record_id}/results", headers=headers)
    actual = json.loads(r.data.decode("utf-8"))
    assert r.status_code == 200, r.data
    # SH Batch API saves the JSON file with request info upon creation, but our openEO driver
    # doesn't include it in the "assets" or elsewhere in the response to /jobs/<job_id>/results
    # Our openEO driver saves metadata.json in the bucket when /jobs/<job_id>/results is accessed,
    # but the signed url for it is added to the "links" in the response to /jobs/<job_id>/results
    expected_num_assets = 0
    assert len(actual["assets"]) == expected_num_assets

    r = app_client.post(f"/jobs/{record_id}/results", headers=headers)
    assert r.status_code == 202, r.data

    r = app_client.delete(f"/jobs/{record_id}/results", headers=headers)
    assert r.status_code == 204, r.data


@with_mocked_auth
@with_mocked_reporting
@with_mocked_batch_request_info
def test_using_user_defined_process(
    app_client, fahrenheit_to_celsius_process, process_graph_with_udp, example_authorization_header_with_oidc
):
    """
    Save a user-defined process and use it in a job
    """
    # Save a user-defined process with unknown parameters
    process_graph_id = "fahrenheit_to_celsius"
    process_graph, _ = fahrenheit_to_celsius_process
    data = {
        "summary": "Convert fahrenheit_to_celsius",
        "process_graph": process_graph,
    }
    r = app_client.put(
        f"/process_graphs/{process_graph_id}",
        data=json.dumps(data),
        headers=example_authorization_header_with_oidc,
        content_type="application/json",
    )
    assert r.status_code == 200, r.data

    data = {
        "process": {
            "process_graph": process_graph_with_udp,
        }
    }
    # Test synchrounous job
    r = app_client.post(
        "/result",
        data=json.dumps(data),
        headers=example_authorization_header_with_oidc,
        content_type="application/json",
    )
    assert r.status_code == 200, r.data
    # Test batch job
    r = app_client.post(
        "/jobs", data=json.dumps(data), headers=example_authorization_header_with_oidc, content_type="application/json"
    )
    assert r.status_code == 201, r.data
    job_id = r.headers["OpenEO-Identifier"]

    r = app_client.post(f"/jobs/{job_id}/results", headers=example_authorization_header_with_oidc)
    assert r.status_code == 202, r.data
    # Test XYZ service
    data["type"] = "xyz"
    data["configuration"] = {"tile_size": 16}
    r = app_client.post(
        "/services",
        data=json.dumps(data),
        content_type="application/json",
        headers=example_authorization_header_with_oidc,
    )
    assert r.status_code == 201, r.data
    service_id = r.headers["OpenEO-Identifier"]

    r = app_client.get("/service/xyz/{}/16/35321/23318".format(service_id))
    assert r.status_code == 200, r.data


def test_process_graph_with_partially_defined_processes(app_client, get_expected_data):
    process_graph = {
        "process_graph": {
            "load1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l1c",
                    "spatial_extent": {
                        "west": 14.012098111544269,
                        "east": 14.04114609486048,
                        "south": 45.99432492799059,
                        "north": 46.00774118321607,
                    },
                    "temporal_extent": ["2022-06-24T00:00:00Z", "2022-07-03T00:00:00Z"],
                    "bands": ["B01"],
                    "properties": {},
                },
            },
            "filter2": {
                "process_id": "filter_bbox",
                "arguments": {
                    "data": {"from_node": "load1"},
                    "extent": {
                        "west": 14.027422184782331,
                        "east": 14.028779372020717,
                        "south": 46.00127415536559,
                        "north": 46.003586149311445,
                    },
                },
            },
            "save3": {
                "process_id": "save_result",
                "arguments": {"data": {"from_node": "filter2"}, "format": "GTIFF"},
                "result": True,
            },
        }
    }
    headers = {"Authorization": f"Bearer basic//{valid_sh_token}"}
    r = app_client.post(
        "/result",
        data=json.dumps({"process": process_graph}),
        headers=headers,
        content_type="application/json",
    )
    assert r.status_code == 200, r.data
    expected_data = get_expected_data("partially_defined_process_result.tiff")
    assert r.data == expected_data


@with_mocked_auth
@pytest.mark.parametrize(
    "collection_id,expected_deployment_endpoint,expected_bucket_name",
    [
        ("sentinel-2-l1c", "https://services.sentinel-hub.com", "com.sinergise.openeo.results.dev"),
        ("corine-land-cover", "https://creodias.sentinel-hub.com", "com.sinergise.openeo.results"),
        ("landsat-7-etm+-l2", "https://services-uswest2.sentinel-hub.com", "com.sinergise.openeo.results.uswest2.dev"),
    ],
)
def test_job_saving_data(
    app_client, get_process_graph, collection_id, expected_deployment_endpoint, expected_bucket_name
):
    data = {
        "process": {
            "process_graph": get_process_graph(
                collection_id=collection_id,
            ),
        }
    }
    headers = {"Authorization": f"Bearer basic//{valid_sh_token}"}

    r = app_client.post(
        "/jobs",
        data=json.dumps(data),
        headers=headers,
        content_type="application/json",
    )
    assert r.status_code == 201, r.data

    record_id = r.headers["OpenEO-Identifier"]

    job_data = JobsPersistence.get_by_id(record_id)
    batch_request_id = job_data["batch_request_id"]
    deployment_endpoint = job_data["deployment_endpoint"]

    assert deployment_endpoint == expected_deployment_endpoint

    bucket = get_bucket(deployment_endpoint)

    assert bucket.bucket_name == expected_bucket_name

    all_data = bucket.get_data_from_bucket(prefix=batch_request_id)
    assert len(all_data) == 1 and all_data[0]["Key"].endswith(
        ".json"
    )  # Upon creation of the batch request, JSON with metadata is saved to bucket

    bucket.generate_presigned_url(all_data[0]["Key"])
    bucket.delete_objects(all_data)

    all_data = bucket.get_data_from_bucket(prefix=batch_request_id)
    assert len(all_data) == 0


@with_mocked_auth
def test_describe_account(app_client, example_authorization_header_with_oidc):
    r = app_client.get("/me")
    assert r.status_code == 401, r.data

    r = app_client.get("/me", headers=example_authorization_header_with_oidc)
    assert r.status_code == 200, r.data
    data = json.loads(r.data.decode("utf-8"))
    assert "user_id" in data, data
    assert data["user_id"] == "example-id"
    assert "info" in data and "oidc_userinfo" in data["info"]

    r = app_client.get("/me", headers={"Authorization": f"Bearer basic//{valid_sh_token}"})
    assert r.status_code == 200, r.data
    data = json.loads(r.data.decode("utf-8"))
    assert "user_id" in data, data
    assert "info" in data and "sh_userinfo" in data["info"]


@with_mocked_auth
@pytest.mark.parametrize(
    "spatial_extent, is_error",
    [
        ({"east": 6.11, "north": 46.17, "south": 46.16, "west": 6.1}, False),
        (
            {
                "east": 6.11111111111113,
                "north": 46.11111111111113,
                "south": 46.11111111111112,
                "west": 6.11111111111112,
            },
            True,
        ),
    ],
)
def test_sync_jobs_imagesize(
    app_client, example_process_graph, example_authorization_header_with_oidc, spatial_extent, is_error
):
    """ """
    example_process_graph["loadco1"]["arguments"]["spatial_extent"] = spatial_extent

    data = {
        "process": {
            "process_graph": example_process_graph,
        }
    }

    r = app_client.post(
        "/result",
        data=json.dumps(data),
        headers=example_authorization_header_with_oidc,
        content_type="application/json",
    )
    if is_error:
        assert r.status_code == ImageDimensionInvalid.http_code, r.data
        assert ImageDimensionInvalid.error_code in r.data.decode("utf-8")
    else:
        assert r.status_code == 200, r.data
