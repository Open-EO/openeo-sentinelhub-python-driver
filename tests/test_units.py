from setup_tests import *
from datetime import datetime

from openeoerrors import (
    AuthenticationRequired,
    AuthenticationSchemeInvalid,
    Internal,
    CredentialsInvalid,
    ProcessParameterInvalid,
    TokenInvalid,
)
from processing.utils import inject_variables_in_process_graph


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
    process = Process({"process_graph": get_process_graph(collection_id=collection_id, bands=bands)})
    tiling_grid_id, tiling_grid_resolution = process.get_appropriate_tiling_grid_and_resolution()

    assert expected_tiling_grid_id == tiling_grid_id
    assert expected_tiling_grid_resolution == tiling_grid_resolution
