from setup_tests import *
from datetime import datetime, timedelta, timezone

from shapely.geometry import shape, mapping

from openeoerrors import (
    AuthenticationRequired,
    AuthenticationSchemeInvalid,
    Internal,
    CredentialsInvalid,
    ProcessParameterInvalid,
    TokenInvalid,
    UnsupportedGeometry,
    TemporalExtentError,
)
from processing.utils import inject_variables_in_process_graph, validate_geojson, parse_geojson
from processing.sentinel_hub import SentinelHub
from processing.partially_supported_processes import FilterBBox, FilterSpatial, ResampleSpatial
from processing.processing_api_request import ProcessingAPIRequest
from processing.openeo_process_errors import NoDataAvailable
from processing.const import ProcessingRequestTypes
from fixtures.geojson_fixtures import GeoJSON_Fixtures
from utils import get_roles

from flask import g
from authentication.user import User


@pytest.mark.parametrize(
    "collection_id",
    ["sentinel-2-l1c", "landsat-7-etm+-l2", "corine-land-cover"],
)
def test_collections(get_process_graph, collection_id):
    all_bands = collections.get_collection(collection_id)["cube:dimensions"]["bands"]["values"]
    process = Process(
        {"process_graph": get_process_graph(collection_id=collection_id, bands=None)},
        request_type=ProcessingRequestTypes.SYNC,
    )
    assert process.evalscript.input_bands == all_bands

    example_bands = ["B01", "B02"]
    process = Process(
        {"process_graph": get_process_graph(collection_id=collection_id, bands=example_bands)},
        request_type=ProcessingRequestTypes.SYNC,
    )
    assert process.evalscript.input_bands == example_bands


@responses.activate
@pytest.mark.parametrize(
    "url,directory,expected_collection_ids",
    [
        ("http://some-url", None, ["a", "b", "c"]),
        (
            None,
            "../../tests/fixtures/collection_information",
            [
                "SPOT",
                "PLEIADES",
                "WORLDVIEW",
                "PLANETSCOPE",
                "landsat-7-etm+-l2",
                "sentinel-2-l1c",
                "corine-land-cover",
                "S2L1C",
                "SENTINEL2_L1C",
                "SENTINEL2_L1C_SENTINELHUB",
                "SENTINEL2_L2A",
                "SENTINEL2_L2A_SENTINELHUB",
                "mapzen-dem",
                "sentinel-3-l1b-slstr",
                "sentinel-1-grd",
            ],
        ),
    ],
)
def test_collections_provider(url, directory, expected_collection_ids):
    # this gets all jsons in the directory
    collections_provider = CollectionsProvider("test", url=url, directory=directory)
    if url is not None:
        responses.add(
            responses.GET,
            url,
            json=[
                {"id": collection_id, "link": f"http://some-url/{collection_id}"}
                for collection_id in expected_collection_ids
            ],
        )
        for collection_id in expected_collection_ids:
            responses.add(responses.GET, f"http://some-url/{collection_id}", json={"id": collection_id})

    collections = collections_provider.load_collections()
    collection_ids = [collection["id"] for collection in collections]
    assert sorted(collection_ids) == sorted(expected_collection_ids)


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
        (
            {
                "sub": "example@egi.eu",
                "eduperson_entitlement": [
                    "urn:mace:egi.eu:group:vo.openeo.cloud:role=member#aai.egi.eu",
                    "urn:mace:egi.eu:group:vo.openeo.cloud:role=vm_operator#aai.egi.eu",
                    "urn:mace:egi.eu:group:vo.openeo.cloud:role=early_adopter#aai.egi.eu",
                    "urn:mace:egi.eu:group:vo.openeo.cloud:admins:role=member#aai.egi.eu",
                    "urn:mace:egi.eu:group:vo.openeo.cloud:admins:role=owner#aai.egi.eu",
                ],
            },
            {"Authorization": "Bearer oidc/egi/<token>"},
            False,
            None,
            None,
        ),
    ],
)
def test_authentication_provider_oidc(oidc_user_info_response, headers, should_raise_error, error, func):
    authentication_provider = AuthenticationProvider(
        oidc_providers=[{"id": "egi", "issuer": "https://aai.egi.eu/auth/realms/egi/"}]
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
                    "https://aai.egi.eu/auth/realms/egi/.well-known/openid-configuration",
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
                    "https://aai.egi.eu/auth/realms/egi/.well-known/openid-configuration",
                    json={"userinfo_endpoint": "http://dummy_userinfo_endpoint"},
                )
                responses.add(responses.GET, "http://dummy_userinfo_endpoint", json=oidc_user_info_response)
                assert authentication_provider.with_bearer_auth(func)()

        execute()


expired_sh_token = "eyJraWQiOiJzaCIsImFsZyI6IlJTMjU2In0.eyJzdWIiOiIzM2ExOWY2ZC1mYTM3LTQ2ZTAtOTk3Yy04OWQ0YTc5MDllMDgiLCJhdWQiOiIyMGI2NTZmOS02NGNjLTQzM2EtYmJjYi1lOTFlODZjN2E3NTciLCJqdGkiOiI1ZTdhODliMS03YWVmLTRjZmYtYTUzZi0zYjQ3ZGZiNjVhZTMiLCJleHAiOjE2NDk4NzI5NDAsIm5hbWUiOiJFTyBCcm93c2VyIGFwcCAiLCJlbWFpbCI6ImluZm8rZW9icm93c2VyQHNlbnRpbmVsLWh1Yi5jb20iLCJnaXZlbl9uYW1lIjoiRU8gQnJvd3NlciBhcHAiLCJmYW1pbHlfbmFtZSI6IiIsInNpZCI6IjI4NTkwZDMxLTUxN2UtNGZjMC1hY2NiLTdiMTM2YWU3MWU0NiIsIm9yZyI6ImE1MmNlNmRhLTIyOTAtNDdjMi04NGIxLTVmZDU4OWRhYWMyNSIsImRpZCI6MSwiYWlkIjoiZTViNWU2NjUtMzZhNy00NjI3LWIzYjUtNWI2M2MwYjkyNjlmIiwiZCI6eyIxIjp7InJhIjp7InJhZyI6NH0sInQiOjE0MDAwfX19.e-3w6Q_NJ8LmRkTczHtvfOCxFocrn2MD2PG4dV5bTSCAS1YAP2c8eFSvQgQUCmuxCEZScIXY1FviWyGF5toAL5c3nlpBeN_lG0meaQz6_PO6943h58dxNVdT8lto4dBZLR1QKydP8OWUS9GuKXXk3JjplqIlBmjHz7sSGzPD8nWMl1uuD07tRhnY382q_wEQ61mw4GdVinm4azotgERSGbCjGlSQzlf75GQKT4HpOmoY26tgbf19HRmr0aQ-QUd8dxUuq6LuY83XmAeok7G9eGxx3BmQnySQlfAJE2oQ31jaxX2q3kR-7riSFD2r5o1Qq4vFwW7yTOSj8o9FqT5LJQ"


@pytest.mark.parametrize(
    "headers,should_raise_error,error,func",
    [
        (
            {"Authorization": f"Bearer basic//{valid_sh_token}"},
            False,
            None,
            None,
        ),
        (
            {"Authorization": f"Bearer basic//{expired_sh_token}"},
            True,
            TokenInvalid,
            None,
        ),
        (
            {"Authorization": f"Bearer basic//<invalid-token>"},
            True,
            TokenInvalid,
            None,
        ),
        (
            {"Authorization": f"Bearer basic/{valid_sh_token}"},
            True,
            AuthenticationSchemeInvalid,
            None,
        ),
    ],
)
def test_authentication_provider_basic(headers, should_raise_error, error, func):
    authentication_provider = AuthenticationProvider()

    if func is None:
        func = lambda: True

    with app.test_request_context("/", headers=headers):
        # Decorating test_authentication_provider outside this context with responses.activate causes an error
        if should_raise_error:
            with pytest.raises(error) as e:
                authentication_provider.with_bearer_auth(func)()

        else:
            assert authentication_provider.with_bearer_auth(func)()


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
                    "collection_id": "sentinel-3-l1b-slstr",
                    "bands": ["F1"],
                    "spatial_extent": {
                        "west": 13.491039,
                        "east": 13.527775,
                        "north": 41.931656,
                        "south": 41.909687,
                    },  # 3.04Km X 2.4Km bbox
                }
            },
            [3, 2],
        ),
        (
            {
                "params": {
                    "collection_id": "sentinel-3-l1b-slstr",
                    "bands": ["S1"],
                    "spatial_extent": {
                        "west": 13.491039,
                        "east": 13.527775,
                        "north": 41.931656,
                        "south": 41.909687,
                    },  # 3.04Km X 2.4Km bbox
                }
            },
            [6, 4],
        ),
        (
            {
                "params": {
                    "collection_id": "sentinel-1-grd",
                    "bands": ["VV"],
                    "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                }
            },
            [3361, 15159],
        ),
        (
            {
                "params": {
                    "collection_id": "sentinel-1-grd",
                    "bands": ["VV"],
                    "spatial_extent": {
                        "west": 11.207085,
                        "east": 22.259331,
                        "north": 43.406606,
                        "south": 38.326104,
                    },  # 892Km X 565Km bbox
                }
            },
            [89203, 56544],
        ),
        (
            {
                "params": {
                    "collection_id": "mapzen-dem",
                    "bands": ["DEM"],
                    "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                }
            },
            [1120, 5053],
        ),
        (
            {
                "params": {
                    "collection_id": "mapzen-dem",
                    "bands": ["DEM"],
                    "spatial_extent": {
                        "west": 13.491039,
                        "east": 13.527775,
                        "north": 41.931656,
                        "south": 41.909687,
                    },  # 3.04Km X 2.4Km bbox
                }
            },
            [100, 77],
        ),
    ],
)
def test_dimensions(get_process_graph, fixture, expected_result):
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
        request_type=ProcessingRequestTypes.SYNC,
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
                },
                request_type=ProcessingRequestTypes.SYNC,
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
            },
            request_type=ProcessingRequestTypes.SYNC,
        )
        assert process.sample_type.value == expected_sample_type


@pytest.mark.parametrize(
    "collection_id,bands,expected_tiling_grid_id,expected_tiling_grid_resolution",
    [
        ("sentinel-2-l1c", ["B01"], 0, 60),
        ("sentinel-2-l1c", ["B01", "B05"], 1, 20),
        ("sentinel-2-l1c", ["B01", "B02"], 1, 10),
        ("sentinel-2-l1c", ["B01", "CLM"], 0, 60),
        ("sentinel-2-l1c", ["CLM"], 2, 120),
        ("sentinel-2-l1c", ["sunAzimuthAngles"], 2, 360),
    ],
)
def test_tiling_grids(
    get_process_graph, collection_id, bands, expected_tiling_grid_id, expected_tiling_grid_resolution
):
    process = Process(
        {"process_graph": get_process_graph(collection_id=collection_id, bands=bands)},
        request_type=ProcessingRequestTypes.BATCH,
    )
    tiling_grid_id, tiling_grid_resolution = process.get_appropriate_tiling_grid_and_resolution()

    assert expected_tiling_grid_id == tiling_grid_id
    assert expected_tiling_grid_resolution == tiling_grid_resolution


@pytest.mark.parametrize(
    "collection_id,featureflags,should_raise_error,error,expected_datacollection_api_id",
    [
        ("sentinel-2-l1c", None, False, None, "sentinel-2-l1c"),
        ("PLANETSCOPE", None, True, Internal, None),
        ("WORLDVIEW", {}, True, Internal, None),
        ("PLEIADES", {"byoc_collection_id": "byoc-some-id"}, False, None, "byoc-some-id"),
    ],
)
def test_get_collection(
    get_process_graph, collection_id, featureflags, should_raise_error, error, expected_datacollection_api_id
):
    if should_raise_error:
        with pytest.raises(error) as e:
            process = Process(
                {"process_graph": get_process_graph(collection_id=collection_id, featureflags=featureflags)},
                request_type=ProcessingRequestTypes.SYNC,
            )
    else:
        process = Process(
            {"process_graph": get_process_graph(collection_id=collection_id, featureflags=featureflags)},
            request_type=ProcessingRequestTypes.SYNC,
        )
        assert process.collection.api_id == expected_datacollection_api_id


@responses.activate
@pytest.mark.parametrize(
    "access_token",
    ["<some-token>"],
)
def test_sentinel_hub_access_token(access_token):
    with app.test_request_context("/"):
        # we need flask g object with user so that g.user.report_usage exists
        # in ProcessingAPIRequest.fetch() for sync jobs

        example_token = "example"

        responses.add(
            responses.POST,
            "https://services.sentinel-hub.com/oauth/token",
            body=json.dumps({"access_token": example_token, "expires_at": 2147483647}),
        )

        responses.add(
            responses.POST,
            "https://services.sentinel-hub.com/api/v1/process",
            headers={"x-processingunits-spent": "1"},
            match=[
                matchers.header_matcher(
                    {"Authorization": f"Bearer {access_token if access_token is not None else example_token}"}
                )
            ],
        )
        responses.add(
            responses.POST,
            "https://services.sentinel-hub.com/api/v1/batch/process",
            json={"id": "example", "processRequest": {}, "status": "CREATED", "tileCount": 1},
            match=[
                matchers.header_matcher(
                    {"Authorization": f"Bearer {access_token if access_token is not None else example_token}"}
                )
            ],
        )

        user = SHUser(user_id="mocked_id", sh_access_token=access_token, sh_userinfo={"d": {"1": {"t": 11000}}})
        g.user = user

        sh = SentinelHub(user=user)
        sh.create_processing_request(
            bbox=BBox((1, 2, 3, 4), crs=CRS.WGS84),
            collection=DataCollection.SENTINEL2_L2A,
            evalscript="",
            from_date=datetime.now(),
            to_date=datetime.now(),
            width=1,
            height=1,
            mimetype=MimeType.PNG,
        )
        sh = SentinelHub(user=user)
        sh.create_batch_job(
            collection=DataCollection.SENTINEL2_L2A,
            evalscript="",
            from_date=datetime.now(),
            to_date=datetime.now(),
            tiling_grid_id=1,
            tiling_grid_resolution=20,
            mimetype=MimeType.PNG,
        )


@pytest.mark.parametrize(
    "collection_id,expected_from_time,expected_to_time",
    [
        (
            "sentinel-2-l1c",
            datetime(2015, 11, 1, tzinfo=timezone.utc),
            datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
        ),
        ("corine-land-cover", datetime(1986, 1, 1, tzinfo=timezone.utc), datetime(2018, 12, 31, tzinfo=timezone.utc)),
        (
            "landsat-7-etm+-l2",
            datetime(1999, 4, 1, tzinfo=timezone.utc),
            datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
        ),
        (
            "mapzen-dem",
            datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
            datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
        ),
    ],
)
def test_get_maximum_temporal_extent(get_process_graph, collection_id, expected_from_time, expected_to_time):
    process = Process(
        {"process_graph": get_process_graph(collection_id=collection_id)}, request_type=ProcessingRequestTypes.SYNC
    )
    from_time, to_time = process.get_maximum_temporal_extent_for_collection()

    assert expected_from_time == from_time
    assert expected_to_time == to_time


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
def test_temporal_extent(get_process_graph, fixture, expected_result):
    if type(expected_result) == type and issubclass(expected_result, Exception):
        with pytest.raises(expected_result):
            process = Process(
                {
                    "process_graph": get_process_graph(
                        collection_id=fixture["params"]["collection_id"],
                        bands=None,
                        temporal_extent=fixture["params"]["temporal_extent"],
                    )
                },
                request_type=ProcessingRequestTypes.SYNC,
            )
    else:
        process = Process(
            {
                "process_graph": get_process_graph(
                    collection_id=fixture["params"]["collection_id"],
                    bands=None,
                    temporal_extent=fixture["params"]["temporal_extent"],
                )
            },
            request_type=ProcessingRequestTypes.SYNC,
        )
        assert process.from_date == expected_result["from_date"]
        assert process.to_date == expected_result["to_date"]


@pytest.mark.parametrize(
    "filename,expected_roles",
    [
        ("1235467/abc.json", ["metadata"]),
        ("abc.json", ["metadata"]),
        ("abc.JSON", ["metadata"]),
        ("1235467/abc.tiff", ["data"]),
        ("abc.png", ["data"]),
        ("abc.jpg", ["data"]),
    ],
)
def test_get_roles(filename, expected_roles):
    roles = get_roles(filename)
    assert roles == expected_roles


@pytest.mark.parametrize(
    "endpoint,access_token,api_responses,min_exec_time,should_raise_error,expected_error",
    [
        ("https://services.sentinel-hub.com", None, [{"status": 200}], 0, False, None),
        (
            "https://services.sentinel-hub.com",
            None,
            [
                {"status": 429, "headers": {"retry-after": "2"}},
                {"status": 429, "headers": {"retry-after": "7"}},
                {"status": 200},
            ],
            9,
            False,
            None,
        ),
        (
            "https://services.sentinel-hub.com",
            None,
            [
                {"status": 429, "headers": {"retry-after": "2"}},
                {"status": 429, "headers": {"retry-after": "2"}},
                {"status": 429, "headers": {"retry-after": "2"}},
                {"status": 429, "headers": {"retry-after": "2"}},
            ],
            0,
            True,
            "Out of retries.",
        ),
        (
            "https://services.sentinel-hub.com",
            None,
            [{"status": 429, "headers": {"retry-after": "2"}}, {"status": 500}],
            0,
            True,
            "Internal Server Error",
        ),
        ("https://services-uswest2.sentinel-hub.com", None, [{"status": 200}], 0, False, None),
        (
            "https://services-uswest2.sentinel-hub.com",
            None,
            [
                {"status": 429, "headers": {"retry-after": "2"}},
                {"status": 429, "headers": {"retry-after": "7"}},
                {"status": 200},
            ],
            9,
            False,
            None,
        ),
        (
            "https://services-uswest2.sentinel-hub.com",
            None,
            [
                {"status": 429, "headers": {"retry-after": "2"}},
                {"status": 429, "headers": {"retry-after": "2"}},
                {"status": 429, "headers": {"retry-after": "2"}},
                {"status": 429, "headers": {"retry-after": "2"}},
            ],
            0,
            True,
            "Out of retries.",
        ),
        (
            "https://services-uswest2.sentinel-hub.com",
            None,
            [{"status": 429, "headers": {"retry-after": "2"}}, {"status": 500}],
            0,
            True,
            "Internal Server Error",
        ),
        ("https://creodias.sentinel-hub.com", None, [{"status": 200}], 0, False, None),
        (
            "https://creodias.sentinel-hub.com",
            None,
            [
                {"status": 429, "headers": {"retry-after": "2"}},
                {"status": 429, "headers": {"retry-after": "7"}},
                {"status": 200},
            ],
            9,
            False,
            None,
        ),
        (
            "https://creodias.sentinel-hub.com",
            None,
            [
                {"status": 429, "headers": {"retry-after": "2"}},
                {"status": 429, "headers": {"retry-after": "2"}},
                {"status": 429, "headers": {"retry-after": "2"}},
                {"status": 429, "headers": {"retry-after": "2"}},
            ],
            0,
            True,
            "Out of retries.",
        ),
        (
            "https://creodias.sentinel-hub.com",
            None,
            [{"status": 429, "headers": {"retry-after": "2"}}, {"status": 500}],
            0,
            True,
            "Internal Server Error",
        ),
    ],
)
def test_processing_api_request(
    endpoint, access_token, api_responses, min_exec_time, should_raise_error, expected_error
):
    @responses.activate(registry=OrderedRegistry)
    def run(endpoint, access_token, api_responses, min_exec_time, should_raise_error, expected_error):
        example_token = "example"
        MAX_RETRIES = 3
        url = f"{endpoint}/api/v1/process"
        user = (
            SHUser(sh_access_token=access_token, sh_userinfo={"d": {"1": {"t": 11000}}})
            if access_token is not None
            else User()
        )

        for response in api_responses:
            responses.add(
                responses.POST,
                url,
                status=response["status"],
                headers=response.get("headers"),
                match=[
                    matchers.header_matcher(
                        {
                            "Authorization": f"Bearer {access_token if access_token is not None else user.session.token['access_token']}"
                        }
                    )
                ],
            )

        try:
            start_time = time.time()
            r = ProcessingAPIRequest(url, {}, user=user, max_retries=MAX_RETRIES).make_request()
            end_time = time.time()
            r.raise_for_status()
            assert r.status_code == 200, r.content
            assert end_time - start_time > min_exec_time
        except Exception as e:
            if not should_raise_error:
                raise
            assert expected_error in str(e)

    run(endpoint, access_token, api_responses, min_exec_time, should_raise_error, expected_error)


@pytest.mark.parametrize(
    "process_graph,expected_is_usage_valid,expected_error,expected_geometry,expected_crs",
    [
        (
            {
                "loadco1": {
                    "process_id": "load_collection",
                    "arguments": {
                        "id": "S2L1C",
                        "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                        "temporal_extent": ["2017-01-01", "2017-02-01"],
                        "bands": ["B01", "B02"],
                    },
                },
                "filterbbox2": {
                    "process_id": "filter_bbox",
                    "arguments": {
                        "data": {"from_node": "loadco1"},
                        "extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                    },
                },
                "saveres1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "filterbbox2"}, "format": "gtiff"},
                    "result": True,
                },
            },
            True,
            None,
            shape(
                {
                    "type": "Polygon",
                    "coordinates": [[[16.1, 47.2], [16.6, 47.2], [16.6, 48.6], [16.1, 48.6], [16.1, 47.2]]],
                }
            ),
            4326,
        ),
        (
            {
                "loadco1": {
                    "process_id": "load_collection",
                    "arguments": {
                        "id": "S2L1C",
                        "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                        "temporal_extent": ["2017-01-01", "2017-02-01"],
                        "bands": ["B01", "B02"],
                    },
                },
                "filterbbox1": {
                    "process_id": "filter_bbox",
                    "arguments": {
                        "data": {"from_node": "loadco1"},
                        "extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                    },
                },
                "mercubes1": {
                    "process_id": "merge_cubes",
                    "arguments": {"cube1": {"from_node": "loadco1"}, "cube2": {"from_node": "filterbbox1"}},
                },
                "saveres1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "mercubes1"}, "format": "gtiff"},
                    "result": True,
                },
            },
            False,
            "Process must be part of the main processing chain.",
            shape(
                {
                    "type": "Polygon",
                    "coordinates": [[[16.1, 47.2], [16.6, 47.2], [16.6, 48.6], [16.1, 48.6], [16.1, 47.2]]],
                }
            ),
            4326,
        ),
        (
            {
                "loadco1": {
                    "process_id": "load_collection",
                    "arguments": {
                        "id": "S2L1C",
                        "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                        "temporal_extent": ["2017-01-01", "2017-02-01"],
                        "bands": ["B01", "B02"],
                    },
                },
                "filterbbox1": {
                    "process_id": "filter_bbox",
                    "arguments": {
                        "data": {"from_node": "loadco1"},
                        "extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                    },
                },
                "filterbbox2": {
                    "process_id": "filter_bbox",
                    "arguments": {
                        "data": {"from_node": "filterbbox1"},
                        "extent": {"west": 13.5, "east": 16.5, "north": 48.5, "south": 47.5},
                    },
                },
                "saveres1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "filterbbox2"}, "format": "gtiff"},
                    "result": True,
                },
            },
            True,
            None,
            shape(
                {
                    "type": "Polygon",
                    "coordinates": [[[16.1, 47.5], [16.5, 47.5], [16.5, 48.5], [16.1, 48.5], [16.1, 47.5]]],
                }
            ),
            4326,
        ),
    ],
)
def test_filter_bbox_process(process_graph, expected_is_usage_valid, expected_error, expected_geometry, expected_crs):
    filter_bbox = FilterBBox(process_graph)
    is_usage_valid, error = filter_bbox.is_usage_valid()
    assert is_usage_valid == expected_is_usage_valid, error
    if not expected_is_usage_valid:
        assert expected_error in error.message
    geometry, crs, resolution, resampling_method = filter_bbox.get_spatial_info()
    assert resolution is None
    assert resampling_method is None
    assert geometry.equals(
        expected_geometry
    ), f"Expected {mapping(expected_geometry)} does not match {mapping(geometry)}"
    assert crs == expected_crs


@pytest.mark.parametrize(
    "process_graph,expected_bbox,expected_crs,expected_geometry,error",
    [
        (
            {
                "loadco1": {
                    "process_id": "load_collection",
                    "arguments": {
                        "id": "sentinel-2-l1c",
                        "spatial_extent": {"west": 15.1, "east": 19.6, "north": 48.4, "south": 46.2},
                        "temporal_extent": ["2017-01-01", "2017-02-01"],
                        "bands": ["B01", "B02"],
                    },
                },
                "filterbbox1": {
                    "process_id": "filter_bbox",
                    "arguments": {
                        "data": {"from_node": "loadco1"},
                        "extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                    },
                },
                "filterbbox2": {
                    "process_id": "filter_bbox",
                    "arguments": {
                        "data": {"from_node": "filterbbox1"},
                        "extent": {"west": 13.5, "east": 16.5, "north": 48.5, "south": 47.5},
                    },
                },
                "saveres1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "filterbbox2"}, "format": "gtiff"},
                    "result": True,
                },
            },
            (16.1, 47.5, 16.5, 48.4),
            4326,
            shape(
                {
                    "type": "Polygon",
                    "coordinates": [[[16.1, 47.5], [16.5, 47.5], [16.5, 48.4], [16.1, 48.4], [16.1, 47.5]]],
                }
            ),
            None,
        ),
        (
            {
                "loadco1": {
                    "process_id": "load_collection",
                    "arguments": {
                        "id": "sentinel-2-l1c",
                        "spatial_extent": {
                            "type": "Polygon",
                            "coordinates": [[[15.1, 46.2], [19.6, 46.2], [19.6, 48.4], [15.1, 48.4], [15.1, 46.2]]],
                        },
                        "temporal_extent": ["2017-01-01", "2017-02-01"],
                        "bands": ["B01", "B02"],
                    },
                },
                "filterbbox1": {
                    "process_id": "filter_bbox",
                    "arguments": {
                        "data": {"from_node": "loadco1"},
                        "extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                    },
                },
                "filterbbox2": {
                    "process_id": "filter_bbox",
                    "arguments": {
                        "data": {"from_node": "filterbbox1"},
                        "extent": {"west": 13.5, "east": 16.5, "north": 48.5, "south": 47.5},
                    },
                },
                "saveres1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "filterbbox2"}, "format": "gtiff"},
                    "result": True,
                },
            },
            (16.1, 47.5, 16.5, 48.4),
            4326,
            shape(
                {
                    "type": "Polygon",
                    "coordinates": [[[16.1, 47.5], [16.5, 47.5], [16.5, 48.4], [16.1, 48.4], [16.1, 47.5]]],
                }
            ),
            None,
        ),
        # Same as above, except that coordinates are converted to EPSG3857
        (
            {
                "loadco1": {
                    "process_id": "load_collection",
                    "arguments": {
                        "id": "sentinel-2-l1c",
                        "spatial_extent": {
                            "type": "Polygon",
                            "coordinates": [[[15.1, 46.2], [19.6, 46.2], [19.6, 48.4], [15.1, 48.4], [15.1, 46.2]]],
                        },
                        "temporal_extent": ["2017-01-01", "2017-02-01"],
                        "bands": ["B01", "B02"],
                    },
                },
                "filterbbox1": {
                    "process_id": "filter_bbox",
                    "arguments": {
                        "data": {"from_node": "loadco1"},
                        "extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                    },
                },
                "filterbbox2": {
                    "process_id": "filter_bbox",
                    "arguments": {
                        "data": {"from_node": "filterbbox1"},
                        "extent": {
                            "crs": 3857,
                            "west": 1502813.13,
                            "east": 1836771.60,
                            "north": 6190443.81,
                            "south": 6024072.12,
                        },
                    },
                },
                "saveres1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "filterbbox2"}, "format": "gtiff"},
                    "result": True,
                },
            },
            (1792243.80, 6024072.12, 1836771.60, 6173660.45),
            3857,
            shape(
                {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [1792243.8017717046, 6024072.119999999],
                            [1836771.6000000003, 6024072.119999999],
                            [1836771.6000000003, 6173660.451962931],
                            [1792243.8017717046, 6173660.451962931],
                            [1792243.8017717046, 6024072.119999999],
                        ]
                    ],
                }
            ),
            None,
        ),
        # Spatial extents in loadco1 and filterbbox1 have no overlap so an error should be raised
        (
            {
                "loadco1": {
                    "process_id": "load_collection",
                    "arguments": {
                        "id": "sentinel-2-l1c",
                        "spatial_extent": {
                            "type": "Polygon",
                            "coordinates": [[[15.1, 46.2], [19.6, 46.2], [19.6, 48.4], [15.1, 48.4], [15.1, 46.2]]],
                        },
                        "temporal_extent": ["2017-01-01", "2017-02-01"],
                        "bands": ["B01", "B02"],
                    },
                },
                "filterbbox1": {
                    "process_id": "filter_bbox",
                    "arguments": {
                        "data": {"from_node": "loadco1"},
                        "extent": {"west": 46.1, "east": 46.6, "north": 18.6, "south": 17.2},
                    },
                },
                "saveres1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "filterbbox1"}, "format": "gtiff"},
                    "result": True,
                },
            },
            None,
            None,
            None,
            NoDataAvailable("Requested spatial extent is empty."),
        ),
        (
            {
                "loadco1": {
                    "process_id": "load_collection",
                    "arguments": {
                        "id": "sentinel-2-l1c",
                        "spatial_extent": {
                            "type": "Polygon",
                            "coordinates": [[[15.1, 46.2], [19.6, 46.2], [19.6, 48.4], [15.1, 48.4], [15.1, 46.2]]],
                        },
                        "temporal_extent": ["2017-01-01", "2017-02-01"],
                        "bands": ["B01", "B02"],
                    },
                },
                "filterbbox1": {
                    "process_id": "filter_bbox",
                    "arguments": {
                        "data": {"from_node": "loadco1"},
                        "extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                    },
                },
                "filterspatial": {
                    "process_id": "filter_spatial",
                    "arguments": {
                        "data": {"from_node": "filterbbox1"},
                        "geometries": {
                            "type": "Polygon",
                            "coordinates": [[[16.4, 46.2], [19.6, 46.2], [19.6, 49.4], [16.4, 49.4], [16.4, 46.2]]],
                        },
                    },
                },
                "saveres1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "filterspatial"}, "format": "gtiff"},
                    "result": True,
                },
            },
            (16.4, 47.2, 16.6, 48.4),
            4326,
            shape(
                {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [16.4, 47.2],
                            [16.6, 47.2],
                            [16.6, 48.4],
                            [16.4, 48.4],
                            [16.4, 47.2],
                        ]
                    ],
                }
            ),
            None,
        ),
        (
            {
                "loadco1": {
                    "process_id": "load_collection",
                    "arguments": {
                        "id": "sentinel-2-l1c",
                        "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                        "temporal_extent": ["2017-01-01", "2017-02-01"],
                        "bands": ["B01", "B02"],
                    },
                },
                "resamplespatial1": {
                    "process_id": "resample_spatial",
                    "arguments": {
                        "data": {"from_node": "loadco1"},
                        "resolution": 10,
                        "projection": 3857,
                        "method": "cubic",
                    },
                },
                "saveres1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "resamplespatial1"}, "format": "gtiff"},
                    "result": True,
                },
            },
            (1792243.801771, 5974780.482145, 1847903.547168, 6207260.308175),
            3857,
            None,
            None,
        ),
    ],
)
def test_get_bounds(process_graph, expected_bbox, expected_crs, expected_geometry, error):
    try:
        process = Process({"process_graph": process_graph}, request_type=ProcessingRequestTypes.SYNC)
        assert pytest.approx(process.bbox) == expected_bbox
        assert process.epsg_code == expected_crs
        if not expected_geometry:
            assert process.geometry == expected_geometry
        else:
            assert shape(process.geometry).equals(expected_geometry)
    except Exception as e:
        if error is not None:
            assert type(e) == type(error) and e.args == error.args
        else:
            raise e


@pytest.mark.parametrize(
    "process_graph,expected_is_usage_valid,expected_error,expected_geometry,expected_crs",
    [
        (
            {
                "loadco1": {
                    "process_id": "load_collection",
                    "arguments": {
                        "id": "sentinel-2-l1c",
                        "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                        "temporal_extent": ["2017-01-01", "2017-02-01"],
                        "bands": ["B01", "B02"],
                    },
                },
                "filterspatial1": {
                    "process_id": "filter_spatial",
                    "arguments": {
                        "data": {"from_node": "loadco1"},
                        "geometries": {
                            "type": "Polygon",
                            "coordinates": [[[15.1, 46.7], [19.6, 46.7], [19.6, 48.4], [15.1, 48.4], [15.1, 46.7]]],
                        },
                    },
                },
                "filterspatial2": {
                    "process_id": "filter_spatial",
                    "arguments": {
                        "data": {"from_node": "filterspatial1"},
                        "geometries": {
                            "type": "Polygon",
                            "coordinates": [[[18.1, 46.2], [19.6, 46.2], [19.6, 49.4], [18.1, 49.4], [18.1, 46.2]]],
                        },
                    },
                },
                "saveres1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "filterspatial2"}, "format": "gtiff"},
                    "result": True,
                },
            },
            True,
            None,
            shape(
                {
                    "type": "Polygon",
                    "coordinates": [[[18.1, 46.7], [19.6, 46.7], [19.6, 48.4], [18.1, 48.4], [18.1, 46.7]]],
                }
            ),
            None,
        )
    ],
)
def test_filter_spatial_process(
    process_graph, expected_is_usage_valid, expected_error, expected_geometry, expected_crs
):
    filter_bbox = FilterSpatial(process_graph)
    is_usage_valid, error = filter_bbox.is_usage_valid()
    assert is_usage_valid == expected_is_usage_valid, error
    if not expected_is_usage_valid:
        assert expected_error in error.message
    geometry, crs, resolution, resampling_method = filter_bbox.get_spatial_info()
    assert resolution is None
    assert resampling_method is None
    assert geometry.equals(
        expected_geometry
    ), f"Expected {mapping(expected_geometry)} does not match {mapping(geometry)}"
    assert crs == expected_crs


@pytest.mark.parametrize(
    "process_graph,expected_resolution,expected_crs,expected_resampling_method,error",
    [
        (
            {
                "loadco1": {
                    "process_id": "load_collection",
                    "arguments": {
                        "id": "sentinel-2-l1c",
                        "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                        "temporal_extent": ["2017-01-01", "2017-02-01"],
                        "bands": ["B01", "B02"],
                    },
                },
                "resamplespatial1": {
                    "process_id": "resample_spatial",
                    "arguments": {
                        "data": {"from_node": "loadco1"},
                        "resolution": 10,
                        "projection": 3857,
                        "method": "cubic",
                    },
                },
                "saveres1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "resamplespatial1"}, "format": "gtiff"},
                    "result": True,
                },
            },
            [10, 10],
            3857,
            ResamplingType.BICUBIC,
            None,
        ),
        (
            {
                "loadco1": {
                    "process_id": "load_collection",
                    "arguments": {
                        "id": "sentinel-2-l1c",
                        "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                        "temporal_extent": ["2017-01-01", "2017-02-01"],
                        "bands": ["B01", "B02"],
                    },
                },
                "resamplespatial1": {
                    "process_id": "resample_spatial",
                    "arguments": {
                        "data": {"from_node": "loadco1"},
                        "resolution": [5, 10],
                        "projection": "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext  +no_defs",
                        "method": "bilinear",
                    },
                },
                "saveres1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "resamplespatial1"}, "format": "gtiff"},
                    "result": True,
                },
            },
            [5, 10],
            3857,
            ResamplingType.BILINEAR,
            None,
        ),
        (
            {
                "loadco1": {
                    "process_id": "load_collection",
                    "arguments": {
                        "id": "sentinel-2-l1c",
                        "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                        "temporal_extent": ["2017-01-01", "2017-02-01"],
                        "bands": ["B01", "B02"],
                    },
                },
                "resamplespatial1": {
                    "process_id": "resample_spatial",
                    "arguments": {
                        "data": {"from_node": "loadco1"},
                        "resolution": [5, 10],
                        "projection": 'PROJCS["WGS 84 / Pseudo-Mercator",GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]],PROJECTION["Mercator_1SP"],PARAMETER["central_meridian",0],PARAMETER["scale_factor",1],PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["X",EAST],AXIS["Y",NORTH],EXTENSION["PROJ4","+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext  +no_defs"],AUTHORITY["EPSG","3857"]]',
                        "method": "bilinear",
                    },
                },
                "saveres1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "resamplespatial1"}, "format": "gtiff"},
                    "result": True,
                },
            },
            [5, 10],
            3857,
            ResamplingType.BILINEAR,
            None,
        ),
        (
            {
                "loadco1": {
                    "process_id": "load_collection",
                    "arguments": {
                        "id": "sentinel-2-l1c",
                        "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                        "temporal_extent": ["2017-01-01", "2017-02-01"],
                        "bands": ["B01", "B02"],
                    },
                },
                "resamplespatial1": {
                    "process_id": "resample_spatial",
                    "arguments": {
                        "data": {"from_node": "loadco1"},
                        "resolution": [5, 10],
                        "projection": "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext  +no_defs",
                        "method": "lanczos",
                    },
                },
                "saveres1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "resamplespatial1"}, "format": "gtiff"},
                    "result": True,
                },
            },
            None,
            None,
            None,
            "Method 'lanczos' not among supported resampling methods: ['near','bilinear','cubic']",
        ),
        (
            {
                "loadco1": {
                    "process_id": "load_collection",
                    "arguments": {
                        "id": "sentinel-2-l1c",
                        "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                        "temporal_extent": ["2017-01-01", "2017-02-01"],
                        "bands": ["B01", "B02"],
                    },
                },
                "resamplespatial1": {
                    "process_id": "resample_spatial",
                    "arguments": {"data": {"from_node": "loadco1"}, "method": "near"},
                },
                "saveres1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "resamplespatial1"}, "format": "gtiff"},
                    "result": True,
                },
            },
            None,
            None,
            None,
            "At least 'resolution' or 'projection' must be specified.",
        ),
        (
            {
                "loadco1": {
                    "process_id": "load_collection",
                    "arguments": {
                        "id": "sentinel-2-l1c",
                        "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                        "temporal_extent": ["2017-01-01", "2017-02-01"],
                        "bands": ["B01", "B02"],
                    },
                },
                "resamplespatial1": {
                    "process_id": "resample_spatial",
                    "arguments": {"data": {"from_node": "loadco1"}, "projection": "invalid", "method": "near"},
                },
                "saveres1": {
                    "process_id": "save_result",
                    "arguments": {"data": {"from_node": "resamplespatial1"}, "format": "gtiff"},
                    "result": True,
                },
            },
            None,
            None,
            None,
            "projection is not a valid EPSG code, WKT string or PROJ definition.",
        ),
    ],
)
def test_resample_spatial_process(process_graph, expected_resolution, expected_crs, expected_resampling_method, error):
    try:
        resample_spatial = ResampleSpatial(process_graph)
        geometry, crs, resolution, resampling_method = resample_spatial.get_spatial_info()
    except Exception as e:
        if error:
            assert error in e.message
        else:
            raise e
    else:
        assert geometry is None
        assert crs == expected_crs
        assert resolution == expected_resolution
        assert resampling_method == expected_resampling_method


@pytest.mark.parametrize(
    "process_graph",
    [
        {
            "1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l1c",
                    "spatial_extent": {
                        "west": 14.503132250376241,
                        "south": 45.98989222284457,
                        "east": 14.578437275398317,
                        "north": 46.04381770188389,
                    },
                    "temporal_extent": ["2022-03-26T00:00:00Z", "2022-03-26T23:59:59Z"],
                    "bands": ["B04", "B08"],
                },
            },
            "2": {
                "process_id": "save_result",
                "arguments": {"data": {"from_node": "ndvi4"}, "format": "GTIFF"},
                "result": True,
            },
            "ndvi4": {
                "process_id": "ndvi",
                "arguments": {"data": {"from_node": "1"}, "target_band": "NDVI", "nir": "B08", "red": "B04"},
            },
        }
    ],
)
def test_bands_metadata(process_graph):
    for node in process_graph.values():
        if node["process_id"] == "load_collection":
            collection_id = node["arguments"]["id"]
    bands_metadata = collections.get_collection(collection_id)["summaries"]["eo:bands"]
    process = Process({"process_graph": process_graph}, request_type=ProcessingRequestTypes.SYNC)
    assert process.evalscript.bands_metadata == bands_metadata
