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
            {
                "from_date": datetime(2017, 1, 1, tzinfo=timezone.utc),
                "to_date": datetime(2017, 1, 1, hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc),
            },
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
                "to_date": datetime(2018, 10, 1, hour=10, minute=0, second=0, microsecond=0, tzinfo=timezone.utc),
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
    process = Process(
        {
            "process_graph": get_process_graph(
                collection_id=fixture["params"]["collection_id"],
                bands=None,
                temporal_extent=fixture["params"]["temporal_extent"],
            )
        }
    )
    assert process.from_date == expected_result["from_date"]
    assert process.to_date == expected_result["to_date"]
