from setup_tests import *


@pytest.fixture
def get_process_graph():
    def wrapped(bands=None, collection_id=None):
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
