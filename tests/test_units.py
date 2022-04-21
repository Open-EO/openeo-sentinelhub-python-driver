from setup_tests import *
from datetime import datetime, timezone
from datetime import datetime

from openeoerrors import (
    AuthenticationRequired,
    AuthenticationSchemeInvalid,
    Internal,
    CredentialsInvalid,
    ProcessParameterInvalid,
    UnsupportedGeometry,
)
from processing.utils import inject_variables_in_process_graph, validate_geojson, parse_geojson
from fixtures.geojson_fixtures import GeoJSON_Fixtures


@pytest.fixture
def get_process_graph():
    def wrapped(
        bands=None, collection_id=None, spatial_extent=None, temporal_extent=None, file_format="gtiff", options=None
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
        if temporal_extent:
            process_graph["loadco1"]["arguments"]["temporal_extent"] = temporal_extent
        if spatial_extent:
            process_graph["loadco1"]["arguments"]["spatial_extent"] = spatial_extent
        if options:
            process_graph["result1"]["arguments"]["options"] = options
        return process_graph

    return wrapped


@pytest.mark.parametrize(
    "collection_id",
    ["sentinel-2-l1c", "landsat-7-etm+-l2", "corine-land-cover"],
)
def test_collections(get_process_graph, collection_id):
    all_bands = collections.get_collection(collection_id)["cube:dimensions"]["bands"]["values"]
    process = Process({"process_graph": get_process_graph(collection_id=collection_id, bands=None)})
    assert process.evalscript.input_bands == all_bands

    example_bands = ["B01", "B02"]
    process = Process({"process_graph": get_process_graph(collection_id=collection_id, bands=example_bands)})
    assert process.evalscript.input_bands == example_bands


# @responses.activate
@pytest.mark.parametrize(
    "oidc_user_info_response,headers,should_raise_error,error,func",
    [
        (
            {
                "sub": "example-id",
                "eduperson_entitlement": [
                    "urn:mace:egi.eu:group:vo.openeo.cloud:role=vm_operator#aai.egi.eu",
                    "urn:mace:egi.eu:group:vo.openeo.cloud:role=member#aai.egi.eu",
                    "urn:mace:egi.eu:group:vo.openeo.cloud:role=early_adopter#aai.egi.eu",
                ],
            },
            {"Authorization": "Bearer oidc/egi/<token>"},
            False,
            None,
            None,
        ),
        (None, None, True, AuthenticationRequired, None),
        (None, {"Authorization": "Bearer oidc/non-existent/<token>"}, True, CredentialsInvalid, None),
        (None, {"Authorization": "Bearer <token>"}, True, AuthenticationSchemeInvalid, None),
        (
            {
                "sub": "example-id",
                "eduperson_entitlement": [
                    "urn:mace:egi.eu:group:vo.non.existent.cloud:role=vm_operator#aai.egi.eu",
                ],
            },
            {"Authorization": "Bearer oidc/egi/<token>"},
            True,
            CredentialsInvalid,
            None,
        ),
        (
            {
                "sub": "example-id",
                "eduperson_entitlement": [
                    "urn:mace:egi.eu:group:vo.non.existent.cloud:role=vm_operator#aai.egi.eu",
                    "urn:mace:egi.eu:group:vo.openeo.cloud:role=vm_operator#aai.egi.eu",
                ],
            },
            {"Authorization": "Bearer oidc/egi/<token>"},
            False,
            None,
            lambda user=None: user is not None,
        ),
    ],
)
def test_authentication_provider(oidc_user_info_response, headers, should_raise_error, error, func):
    authentication_provider = AuthenticationProvider(
        oidc_providers=[{"id": "egi", "issuer": "https://aai.egi.eu/oidc/"}]
    )

    if func is None:
        func = lambda: True

    with app.test_request_context("/", headers=headers):
        # Decorating test_authentication_provider outside this context with responses.activate causes an error
        if should_raise_error:

            @responses.activate
            def execute():
                responses.add(
                    responses.GET,
                    "https://aai.egi.eu/oidc/.well-known/openid-configuration",
                    json={"userinfo_endpoint": "http://dummy_userinfo_endpoint"},
                )
                responses.add(responses.GET, "http://dummy_userinfo_endpoint", json=oidc_user_info_response)
                with pytest.raises(error) as e:
                    authentication_provider.with_bearer_auth(func)()

        else:

            @responses.activate
            def execute():
                responses.add(
                    responses.GET,
                    "https://aai.egi.eu/oidc/.well-known/openid-configuration",
                    json={"userinfo_endpoint": "http://dummy_userinfo_endpoint"},
                )
                responses.add(responses.GET, "http://dummy_userinfo_endpoint", json=oidc_user_info_response)
                assert authentication_provider.with_bearer_auth(func)()

        execute()


def test_inject_variables_in_process_graph():
    process_graph = {
        "loadco1": {
            "process_id": "load_collection",
            "arguments": {
                "id": "s2-l2a",
                "spatial_extent": {
                    "west": {"from_parameter": "param_west"},
                    "east": {"from_parameter": "param_east"},
                    "north": {"from_parameter": "param_north"},
                    "south": {"from_parameter": "param_south"},
                },
                "temporal_extent": ["2017-01-01", {"from_parameter": "param_time_to"}],
            },
        },
        "reduce1": {
            "process_id": "reduce_dimension",
            "arguments": {
                "data": {"from_node": "loadco1"},
                "reducer": {
                    "process_graph": {
                        "2": {
                            "process_id": {"from_parameter": "param_process_id"},
                            "arguments": {
                                "data": {"from_parameter": "data"},
                                "context": {"from_parameter": "param_context"},
                            },
                            "result": True,
                        }
                    }
                },
                "dimension": {"from_parameter": "param_dimension"},
            },
        },
        "result1": {
            "process_id": "save_result",
            "arguments": {
                "data": {"from_node": "reduce1"},
                "format": {"from_parameter": "param_format"},
            },
            "result": True,
        },
    }
    variables = {
        "param_west": 42,
        "param_east": False,
        "param_north": None,
        "param_south": "something",
        "param_time_to": "2018-01-01",
        "param_process_id": -324,
        "param_context": {},
        "param_dimension": ["something"],
        "param_format": "png",
    }

    expected_process_graph = {
        "loadco1": {
            "process_id": "load_collection",
            "arguments": {
                "id": "s2-l2a",
                "spatial_extent": {
                    "west": variables["param_west"],
                    "east": variables["param_east"],
                    "north": variables["param_north"],
                    "south": variables["param_south"],
                },
                "temporal_extent": ["2017-01-01", variables["param_time_to"]],
            },
        },
        "reduce1": {
            "process_id": "reduce_dimension",
            "arguments": {
                "data": {"from_node": "loadco1"},
                "reducer": {
                    "process_graph": {
                        "2": {
                            "process_id": variables["param_process_id"],
                            "arguments": {"data": {"from_parameter": "data"}, "context": variables["param_context"]},
                            "result": True,
                        }
                    }
                },
                "dimension": variables["param_dimension"],
            },
        },
        "result1": {
            "process_id": "save_result",
            "arguments": {
                "data": {"from_node": "reduce1"},
                "format": variables["param_format"],
            },
            "result": True,
        },
    }

    inject_variables_in_process_graph(process_graph, variables)
    assert process_graph == expected_process_graph


@pytest.mark.parametrize(
    "fixture, expected_result",
    [
        (
            {
                "params": {
                    "collection_id": "sentinel-2-l1c",
                    "bands": ["B04"],
                }
            },
            (14627, 2456420),
        ),
        (
            {
                "params": {
                    "collection_id": "sentinel-2-l1c",
                    "bands": ["B07"],
                    "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                }
            },
            (1732, 7813),
        ),
        (
            {
                "params": {
                    "collection_id": "sentinel-2-l1c",
                    "bands": ["B04", "B07"],
                    "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                }
            },
            (3465, 15625),
        ),
        (
            {
                "params": {
                    "collection_id": "corine-land-cover",
                    "bands": ["B04"],
                    "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                }
            },
            (3465, 15625),
        ),
        (
            {
                "params": {
                    "collection_id": "sentinel-2-l1c",
                    "bands": ["B04", "B07"],
                    "width": 256,
                    "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                }
            },
            (256, 15625),
        ),
        (
            {
                "params": {
                    "collection_id": "sentinel-2-l1c",
                    "bands": ["B04", "B07"],
                    "height": 256,
                    "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                }
            },
            (3465, 256),
        ),
        (
            {
                "params": {
                    "collection_id": "sentinel-2-l1c",
                    "bands": ["B04", "B07"],
                    "width": 256,
                    "height": 256,
                    "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                }
            },
            (256, 256),
        ),
        (
            {
                "params": {
                    "collection_id": "sentinel-2-l1c",
                    "bands": ["B04"],
                    "spatial_extent": {"west": 12.725279, "east": 13.928021, "north": 41.417766, "south": 41.579378},
                }
            },
            [10074, 1600],
        ),
        (
            {
                "params": {
                    "collection_id": "sentinel-2-l1c",
                    "bands": ["B04"],
                    "spatial_extent": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [12.786158, 41.939125],
                                [12.795811, 41.942638],
                                [12.810235, 41.938282],
                                [12.799845, 41.933699],
                                [12.786158, 41.939125],
                            ]
                        ],
                    },
                }
            },
            [202, 94],
        ),
        (
            {
                "params": {
                    "collection_id": "sentinel-2-l1c",
                    "bands": ["B04"],
                    "spatial_extent": GeoJSON_Fixtures.multi_polygon,
                }
            },
            [33358, 33241],
        ),
        (
            {
                "params": {
                    "collection_id": "sentinel-2-l1c",
                    "bands": ["B04"],
                    "spatial_extent": GeoJSON_Fixtures.polygon_multi_polygon_feature_collection,
                }
            },
            [33358, 33241],
        ),
        (
            {
                "params": {
                    "collection_id": "sentinel-2-l1c",
                    "bands": ["B04"],
                    "spatial_extent": GeoJSON_Fixtures.polygon_point_feature_collection,
                }
            },
            UnsupportedGeometry,
        ),
    ],
)
def test_dimensions(get_process_graph, fixture, expected_result):
    if type(expected_result) == type and issubclass(expected_result, Exception):
        with pytest.raises(UnsupportedGeometry) as ex:
            process = Process(
                {
                    "process_graph": get_process_graph(
                        collection_id=fixture["params"]["collection_id"],
                        bands=fixture["params"]["bands"],
                        spatial_extent=fixture["params"].get("spatial_extent", None),
                    )
                },
                width=fixture["params"].get("width", None),
                height=fixture["params"].get("height", None),
            )
        assert ex.value.message == expected_result.message
    else:
        process = Process(
            {
                "process_graph": get_process_graph(
                    collection_id=fixture["params"]["collection_id"],
                    bands=fixture["params"]["bands"],
                    spatial_extent=fixture["params"].get("spatial_extent", None),
                )
            },
            width=fixture["params"].get("width", None),
            height=fixture["params"].get("height", None),
        )

        assert expected_result[0] == process.width
        assert expected_result[1] == process.height


@pytest.mark.parametrize(
    "file_format,options,expected_sample_type,should_raise_error,error,error_args",
    [
        ("gtiff", None, "FLOAT32", False, None, None),
        ("PNG", None, "UINT8", False, None, None),
        ("jpeg", None, "UINT8", False, None, None),
        ("gtiff", {"datatype": "byte"}, "UINT8", False, None, None),
        ("GTIFF", {"datatype": "uint16"}, "UINT16", False, None, None),
        ("png", {"datatype": "uint16"}, "UINT16", False, None, None),
        (
            "gtiff",
            {"datatype": "float64"},
            None,
            True,
            ProcessParameterInvalid,
            ("options", "save_result", "float64 is not a supported 'datatype'."),
        ),
        (
            "JPEG",
            {"datatype": "uint16"},
            None,
            True,
            ProcessParameterInvalid,
            ("options", "save_result", "uint16 is not a valid 'datatype' for format JPEG."),
        ),
        (
            "JPEG",
            {"datatype": "float32"},
            None,
            True,
            ProcessParameterInvalid,
            ("options", "save_result", "float32 is not a valid 'datatype' for format JPEG."),
        ),
        (
            "PNG",
            {"datatype": "float32"},
            None,
            True,
            ProcessParameterInvalid,
            ("options", "save_result", "float32 is not a valid 'datatype' for format PNG."),
        ),
    ],
)
def test_sample_type(
    get_process_graph, file_format, options, expected_sample_type, should_raise_error, error, error_args
):
    if should_raise_error:
        with pytest.raises(ProcessParameterInvalid) as ex:
            process = Process(
                {
                    "process_graph": get_process_graph(
                        file_format=file_format,
                        options=options,
                        spatial_extent={"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                        collection_id="sentinel-2-l1c",
                    )
                }
            )
        assert ex.value.args == error_args
    else:
        process = Process(
            {
                "process_graph": get_process_graph(
                    file_format=file_format,
                    options=options,
                    spatial_extent={"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                    collection_id="sentinel-2-l1c",
                )
            }
        )
        assert process.sample_type.value == expected_sample_type


@pytest.mark.parametrize(
    "fixture, expected_result",
    [
        (
            {"params": {"spatial_extent": GeoJSON_Fixtures.polygon}},
            True,
        ),
        (
            {"params": {"spatial_extent": GeoJSON_Fixtures.multi_polygon}},
            True,
        ),
        (
            {"params": {"spatial_extent": GeoJSON_Fixtures.polygon_feature}},
            True,
        ),
        (
            {"params": {"spatial_extent": GeoJSON_Fixtures.multi_polygon_feature}},
            True,
        ),
        (
            {"params": {"spatial_extent": GeoJSON_Fixtures.polygon_feature_collection}},
            True,
        ),
        (
            {"params": {"spatial_extent": GeoJSON_Fixtures.polygon_multi_polygon_feature_collection}},
            True,
        ),
        (
            {"params": {"spatial_extent": GeoJSON_Fixtures.polygon_geometry_collection}},
            True,
        ),
        (
            {"params": {"spatial_extent": GeoJSON_Fixtures.polygon_multi_polygon_geometry_collection}},
            True,
        ),
        (
            {"params": {"spatial_extent": GeoJSON_Fixtures.point}},
            UnsupportedGeometry,
        ),
        (
            {"params": {"spatial_extent": GeoJSON_Fixtures.point_feature}},
            UnsupportedGeometry,
        ),
        (
            {"params": {"spatial_extent": GeoJSON_Fixtures.polygon_point_feature_collection}},
            UnsupportedGeometry,
        ),
        (
            {"params": {"spatial_extent": GeoJSON_Fixtures.polygon_point_geometry_collection}},
            UnsupportedGeometry,
        ),
    ],
)
def test_geojson_validation(fixture, expected_result):
    if type(expected_result) == type and issubclass(expected_result, Exception):
        with pytest.raises(expected_result):
            validate_geojson(fixture["params"]["spatial_extent"])
    else:
        assert validate_geojson(fixture["params"]["spatial_extent"]) == expected_result


@pytest.mark.parametrize(
    "fixture, expected_result",
    [
        (
            {"params": {"spatial_extent": GeoJSON_Fixtures.polygon}},
            GeoJSON_Fixtures.polygon,
        ),
        (
            {"params": {"spatial_extent": GeoJSON_Fixtures.polygon_feature}},
            GeoJSON_Fixtures.polygon,
        ),
        (
            {"params": {"spatial_extent": GeoJSON_Fixtures.multi_polygon}},
            GeoJSON_Fixtures.multi_polygon,
        ),
        (
            {"params": {"spatial_extent": GeoJSON_Fixtures.multi_polygon_feature}},
            GeoJSON_Fixtures.multi_polygon,
        ),
        (
            {"params": {"spatial_extent": GeoJSON_Fixtures.polygon_multi_polygon_feature_collection}},
            {
                "type": "MultiPolygon",
                "coordinates": [
                    GeoJSON_Fixtures.polygon["coordinates"],
                    *GeoJSON_Fixtures.multi_polygon["coordinates"],
                ],
            },
        ),
        (
            {"params": {"spatial_extent": GeoJSON_Fixtures.polygon_multi_polygon_geometry_collection}},
            {
                "type": "MultiPolygon",
                "coordinates": [
                    GeoJSON_Fixtures.polygon["coordinates"],
                    *GeoJSON_Fixtures.multi_polygon["coordinates"],
                ],
            },
        ),
        ({"params": {"spatial_extent": GeoJSON_Fixtures.polygon_point_feature_collection}}, UnsupportedGeometry),
        ({"params": {"spatial_extent": GeoJSON_Fixtures.polygon_point_geometry_collection}}, UnsupportedGeometry),
    ],
)
def test_geojson_parsing(fixture, expected_result):
    if type(expected_result) == type and issubclass(expected_result, Exception):
        with pytest.raises(expected_result):
            parse_geojson(fixture["params"]["spatial_extent"])
    else:
        assert parse_geojson(fixture["params"]["spatial_extent"]) == expected_result


current_date = datetime.now()


@pytest.mark.parametrize(
    "fixture, expected_result",
    [
        (
            {"params": {"collection_id": "sentinel-2-l1c", "temporal_extent": ["2019-01-01", None]}},
            {
                "from_date": datetime(2019, 1, 1, tzinfo=timezone.utc),
                "to_date": datetime(
                    current_date.year,
                    current_date.month,
                    current_date.day,
                    hour=23,
                    minute=59,
                    second=59,
                    microsecond=999999,
                    tzinfo=timezone.utc,
                ),
            },
        ),
        (
            {"params": {"collection_id": "sentinel-2-l1c", "temporal_extent": ["2017-01-01", "2017-01-01"]}},
            TemporalExtentError,
        ),
        (
            {
                "params": {
                    "collection_id": "sentinel-2-l1c",
                    "temporal_extent": ["2018-10-01T00:00:00Z", "2018-10-01T10:00:00Z"],
                }
            },
            {
                "from_date": datetime(2018, 10, 1, tzinfo=timezone.utc),
                "to_date": datetime(2018, 10, 1, hour=9, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc),
            },
        ),
        (
            {"params": {"collection_id": "mapzen-dem", "temporal_extent": None}},
            {
                "from_date": datetime(current_date.year, current_date.month, current_date.day, tzinfo=timezone.utc),
                "to_date": datetime(
                    current_date.year,
                    current_date.month,
                    current_date.day,
                    hour=23,
                    minute=59,
                    second=59,
                    microsecond=999999,
                    tzinfo=timezone.utc,
                ),
            },
        ),
    ],
)
def test_temporal_extend(get_process_graph, fixture, expected_result):
    if type(expected_result) == type and issubclass(expected_result, Exception):
        with pytest.raises(expected_result):
            process = Process(
                {
                    "process_graph": get_process_graph(
                        collection_id=fixture["params"]["collection_id"],
                        bands=None,
                        temporal_extent=fixture["params"]["temporal_extent"],
                    )
                }
            )
    else:
        process = Process(
            {
                "process_graph": get_process_graph(
                    collection_id=fixture["params"]["collection_id"],
                    bands=None,
                    temporal_extent=fixture["params"]["temporal_extent"],
                )
            }
        )
        print(expected_result["from_date"])
        assert process.from_date == expected_result["from_date"]
        assert process.to_date == expected_result["to_date"]
