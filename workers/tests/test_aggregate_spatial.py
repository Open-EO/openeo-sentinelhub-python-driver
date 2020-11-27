from datetime import datetime
import os
import sys

import numpy as np
import pytest
import pandas as pd
from sentinelhub import CRS, BBox

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessParameterInvalid, Band, assert_equal, DataCube, DimensionType
import logging


@pytest.fixture
def execute_process():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    def wrapped(arguments):
        return process.aggregate_spatial.aggregate_spatialEOTask(None, "", logger, {}, "node1", {}).process(arguments)

    return wrapped


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "data,geometries,reducer,target_dimension,expected_result",
    [
        # simple test:
        (
            DataCube(
                [
                    [
                        [0.1, 0.3],
                        [0.2, 0.3],
                        [0.2, 0.3],
                        [0.2, 0.3],
                        [0.1, 0.3],
                    ],
                    [
                        [0.1, 0.3],
                        [22.9, 33.9],
                        [22.9, 33.9],
                        [22.9, 33.9],
                        [0.1, 0.3],
                    ],
                    [
                        [0.1, 0.3],
                        [0.1, 0.3],
                        [0.1, 0.3],
                        [0.1, 0.3],
                        [0.1, 0.3],
                    ],
                ],
                dims=("x", "y", "t"),  # x: 3, y: 5, t: 2
                coords={"t": ["2019-08-16", "2019-08-18"]},
                attrs={"bbox": BBox((5.0, 46.0, 6.0, 47.0), CRS(4326))},
                dim_types={"x": DimensionType.SPATIAL, "y": DimensionType.SPATIAL, "t": DimensionType.TEMPORAL},
            ),
            [
                {
                    "type": "MultiPolygon",
                    "coordinates": [[[[5.4, 46.21], [5.6, 46.21], [5.6, 46.89], [5.4, 46.89], [5.4, 46.21]]]],
                },
                {
                    "type": "MultiPolygon",
                    "coordinates": [[[[5.0, 46.0], [6.0, 46.0], [6.0, 47.0], [5.0, 47.0], [5.0, 46.0]]]],
                },
                {
                    "type": "MultiPolygon",
                    "coordinates": [[[[5.0, 46.21], [5.6, 46.21], [5.6, 46.89], [5.0, 46.89], [5.0, 46.21]]]],
                },
            ],
            {
                "process_graph": {
                    "resolver": {
                        "process_id": "sum",
                        "arguments": {"data": {"from_parameter": "data"}},
                        "result": True,
                    }
                }
            },
            None,
            DataCube(
                [
                    [
                        [3 * 22.9, 3 * 33.9],
                        [3 * 22.9 + 9 * 0.1 + 3 * 0.2, 3 * 33.9 + 12 * 0.3],
                        [3 * 22.9 + 3 * 0.2, 3 * 33.9 + 3 * 0.3],
                    ],
                    [
                        [15, 15],  # number of input pixels
                        [15, 15],
                        [15, 15],
                    ],
                    [
                        [3, 3],  # pixels used (as per geometry)
                        [15, 15],
                        [6, 6],
                    ],
                ],
                dims=("result_meta", "result", "t"),  #
                coords={"t": ["2019-08-16", "2019-08-18"], "result_meta": ["value", "total_count", "valid_count"]},
                attrs={},
                dim_types={
                    "result_meta": DimensionType.OTHER,
                    "result": DimensionType.OTHER,
                    "t": DimensionType.TEMPORAL,
                },
            ),
        ),
        # simple test, single geometry:
        (
            DataCube(
                [
                    [
                        [0.1, 0.3],
                        [0.2, 0.3],
                        [0.2, 0.3],
                        [0.2, 0.3],
                        [0.1, 0.3],
                    ],
                    [
                        [0.1, 0.3],
                        [22.9, 33.9],
                        [22.9, 33.9],
                        [22.9, 33.9],
                        [0.1, 0.3],
                    ],
                    [
                        [0.1, 0.3],
                        [0.1, 0.3],
                        [0.1, 0.3],
                        [0.1, 0.3],
                        [0.1, 0.3],
                    ],
                ],
                dims=("x", "y", "t"),  # x: 3, y: 5, t: 2
                coords={"t": ["2019-08-16", "2019-08-18"]},
                attrs={"bbox": BBox((5.0, 46.0, 6.0, 47.0), CRS(4326))},
                dim_types={"x": DimensionType.SPATIAL, "y": DimensionType.SPATIAL, "t": DimensionType.TEMPORAL},
            ),
            [
                {
                    "type": "MultiPolygon",
                    "coordinates": [[[[5.4, 46.21], [5.6, 46.21], [5.6, 46.89], [5.4, 46.89], [5.4, 46.21]]]],
                },
            ],
            {
                "process_graph": {
                    "resolver": {
                        "process_id": "sum",
                        "arguments": {"data": {"from_parameter": "data"}},
                        "result": True,
                    }
                }
            },
            None,
            DataCube(
                [
                    [
                        [3 * 22.9, 3 * 33.9],
                    ],
                    [
                        [15, 15],
                    ],
                    [
                        [3, 3],
                    ],
                ],
                dims=("result_meta", "result", "t"),  #
                coords={"t": ["2019-08-16", "2019-08-18"], "result_meta": ["value", "total_count", "valid_count"]},
                attrs={},
                dim_types={"x": DimensionType.SPATIAL, "y": DimensionType.SPATIAL, "t": DimensionType.TEMPORAL},
            ),
        ),
    ],
)
def test_correct(execute_process, data, geometries, reducer, target_dimension, expected_result):
    arguments = {
        "data": data,
        "geometries": geometries,
        "reducer": reducer,
    }
    if target_dimension is not None:
        arguments["target_dimension"] = target_dimension

    result = execute_process(arguments)
    assert_equal(result, expected_result)
