from setup_tests import *


@with_mocked_auth
@with_mocked_reporting
def test_xyz_service_2(app_client, example_authorization_header_with_oidc, service_factory):
    process_graph = {
        "loadco1": {
            "process_id": "load_collection",
            "arguments": {
                "id": "sentinel-2-l1c",
                "spatial_extent": {
                    "west": 1,
                    "east": 2,
                    "north": 3,
                    "south": 4,
                },
                "temporal_extent": ["2019-08-01", "2019-08-18"],
                "bands": ["B01", "B02", "B03"],
            },
        },
        "result1": {
            "process_id": "save_result",
            "arguments": {"data": {"from_node": "loadco1"}, "format": "jpeg"},
            "result": True,
        },
    }

    service_id = service_factory(process_graph, title="Test XYZ service", service_type="xyz")

    spatial_extent_with_overwritten_params = {
        "west": {"from_parameter": "spatial_extent_west"},
        "east": {"from_parameter": "spatial_extent_east"},
        "north": {"from_parameter": "spatial_extent_north"},
        "south": {"from_parameter": "spatial_extent_south"},
    }

    # Check hardcoded spatial extent values get overwritten with default parameters
    r = app_client.get(
        "/services/{}".format(service_id),
        content_type="application/json",
        headers=example_authorization_header_with_oidc,
    )
    saved_process_graph = json.loads(r.data.decode("utf-8"))["process"]["process_graph"]

    assert saved_process_graph["loadco1"]["arguments"]["spatial_extent"] == spatial_extent_with_overwritten_params

    # Set one cardinal direction to use a parameter and update the service
    # Check spatial extent doesn't get overwritten

    process_graph2 = deepcopy(process_graph)
    process_graph2["loadco1"]["arguments"]["spatial_extent"]["west"] = {"from_parameter": "spatial_extent_north"}

    r = app_client.patch(
        "/services/{}".format(service_id),
        json={"process": {"process_graph": process_graph2}},
        headers=example_authorization_header_with_oidc,
        content_type="application/json",
    )
    assert r.status_code == 204, r.data

    r = app_client.get(
        "/services/{}".format(service_id),
        content_type="application/json",
        headers=example_authorization_header_with_oidc,
    )
    saved_process_graph = json.loads(r.data.decode("utf-8"))["process"]["process_graph"]

    assert (
        saved_process_graph["loadco1"]["arguments"]["spatial_extent"]
        == process_graph2["loadco1"]["arguments"]["spatial_extent"]
    )

    # Update the service with the original process graph and check spatial extent was overwritten

    r = app_client.patch(
        "/services/{}".format(service_id),
        json={"process": {"process_graph": process_graph}},
        headers=example_authorization_header_with_oidc,
        content_type="application/json",
    )
    assert r.status_code == 204, r.data

    r = app_client.get(
        "/services/{}".format(service_id),
        content_type="application/json",
        headers=example_authorization_header_with_oidc,
    )
    saved_process_graph = json.loads(r.data.decode("utf-8"))["process"]["process_graph"]

    assert saved_process_graph["loadco1"]["arguments"]["spatial_extent"] == spatial_extent_with_overwritten_params
