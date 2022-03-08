from setup_tests import *
from pprint import pprint
from datetime import datetime, timezone


@pytest.fixture
def get_process_graph():
    def wrapped(bands=None, collection_id=None, temporal_extent=None):
        process_graph = {
            "loadco1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": collection_id,
                    "spatial_extent": {"west": 16.1, "east": 16.6, "north": 48.6, "south": 47.2},
                    "temporal_extent": ["2017-01-01", "2017-02-01"],
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
        if temporal_extent:
            process_graph["loadco1"]["arguments"]["temporal_extent"] = temporal_extent
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


current_date = datetime.now()


@pytest.mark.parametrize(
    "fixture, expected_result",
    [
        (
            {"params": {"collection_id": "sentinel-2-l1c", "bands": ["B04"]}},
            (3465, 15625),
        ),
        (
            {"params": {"collection_id": "sentinel-2-l1c", "bands": ["B07"]}},
            (1732, 7813),
        ),
        (
            {"params": {"collection_id": "sentinel-2-l1c", "bands": ["B04", "B07"]}},
            (3465, 15625),
        ),
        (
            {"params": {"collection_id": "corine-land-cover", "bands": ["B04"]}},
            (3465, 15625),
        ),
        (
            {"params": {"collection_id": "sentinel-2-l1c", "bands": ["B04", "B07"], "width": 256}},
            (256, 15625),
        ),
          (
            {"params": {"collection_id": "sentinel-2-l1c", "bands": ["B04", "B07"], "height": 256}},
            (3465, 256),
        ),
           (
            {"params": {"collection_id": "sentinel-2-l1c", "bands": ["B04", "B07"],"width":256, "height": 256}},
            (256, 256),
        ),
    ],
)
def test_dimensions(get_process_graph, fixture, expected_result):
    process = Process(
        {
            "process_graph": get_process_graph(
                collection_id=fixture["params"]["collection_id"],
                bands=fixture["params"]["bands"],
            )
        },
        width=fixture["params"].get("width", None),
        height=fixture["params"].get("height", None),
    )

    assert expected_result[0] == process.width
    assert expected_result[1] == process.height
