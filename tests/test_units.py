from setup_tests import *
from datetime import datetime

from openeoerrors import AuthenticationRequired, AuthenticationSchemeInvalid, Internal, CredentialsInvalid


@pytest.fixture
def get_process_graph():
    def wrapped(bands=None, collection_id=None, spatial_extent=None):
        process_graph = {
            "loadco1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": collection_id,
                    "temporal_extent": ["2017-01-01", "2017-02-01"],
                    "spatial_extent": spatial_extent,
                },
            },
            "result1": {
                "process_id": "save_result",
                "arguments": {
                    "data": {"from_node": "loadco1"},
                    "format": "gtiff",
                },
                "result": True,
            },
        }
        if bands:
            process_graph["loadco1"]["arguments"]["bands"] = bands
        if spatial_extent:
            process_graph["loadco1"]["arguments"]["spatial_extent"] = spatial_extent
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
    authentication_provider.set_testing_oidc_responses(
        oidc_general_info_response={"userinfo_endpoint": ""}, oidc_user_info_response=oidc_user_info_response
    )

    if func is None:
        func = lambda: True

    with app.test_request_context("/", headers=headers):
        if should_raise_error:
            with pytest.raises(error) as e:
                authentication_provider.with_bearer_auth(func)()
        else:
            assert authentication_provider.with_bearer_auth(func)()


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
