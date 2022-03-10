from setup_tests import *
from datetime import datetime

from processing.utils import inject_variables_in_process_graph


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
