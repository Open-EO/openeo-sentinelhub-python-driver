from datetime import datetime
import os
import sys

import numpy as np
import pytest
import xarray as xr

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessParameterInvalid, Band, DataCube, assert_equal, DimensionType


@pytest.fixture
def execute_process():
    def wrapped(arguments):
        return process.add_dimension.add_dimensionEOTask(None, "", None, {}, "node1", {}).process(arguments)

    return wrapped


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "data,name,label,dimension_type,expected_result",
    [
        (
            DataCube(
                [1, 2, 3, 4],
                dims=["t"],
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                        datetime(2014, 3, 7),
                    ]
                },
                dim_types={"t": DimensionType.TEMPORAL},
            ),
            "x",
            42,
            "spatial",
            DataCube(
                [[1, 2, 3, 4]],
                dims=["x", "t"],
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                        datetime(2014, 3, 7),
                    ],
                    "x": [42],
                },
                dim_types={"t": DimensionType.TEMPORAL, "x": DimensionType.SPATIAL},
            ),
        ),
        (
            DataCube(
                [1, 2, 3, 4],
                dims=["t"],
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                        datetime(2014, 3, 7),
                    ]
                },
                dim_types={"t": DimensionType.TEMPORAL},
            ),
            "b",
            "B01",
            "bands",
            DataCube(
                [[1, 2, 3, 4]],
                dims=["b", "t"],
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                        datetime(2014, 3, 7),
                    ],
                    "b": [Band("B01")],
                },
                dim_types={"t": DimensionType.TEMPORAL, "b": DimensionType.BANDS},
            ),
        ),
        (
            DataCube([1, 2, 3, 4], dims=["x"], dim_types={"x": DimensionType.SPATIAL}),
            "t",
            "2020-02-20",
            "temporal",
            DataCube(
                [[1, 2, 3, 4]],
                dims=["t", "x"],
                coords={
                    "t": [
                        datetime(2020, 2, 20),
                    ],
                },
                dim_types={"t": DimensionType.TEMPORAL, "x": DimensionType.SPATIAL},
            ),
        ),
    ],
)
def test_correct(execute_process, data, name, label, dimension_type, expected_result):
    arguments = {"data": data, "name": name, "label": label, "type": dimension_type}
    result = execute_process(arguments)
    assert_equal(result, expected_result)


@pytest.mark.parametrize(
    "data,name,label,dimension_type",
    [
        (
            DataCube(
                [1],
                dims=["t"],
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                    ]
                },
            ),
            "t",
            "2020-02-20",
            "temporal",
        ),
    ],
)
def test_dimension_exists(execute_process, data, name, label, dimension_type):
    arguments = {"data": data, "name": name, "label": label, "type": dimension_type}
    with pytest.raises(ProcessParameterInvalid) as ex:
        result = execute_process(arguments)
    assert ex.value.args == (
        "add_dimension",
        "name",
        "A dimension with the specified name already exists. (DimensionExists)",
    )


@pytest.mark.parametrize(
    "data,name,label,dimension_type",
    [
        (
            DataCube(
                [1],
                dims=["t"],
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                    ]
                },
            ),
            "t",
            "2020-02-20",
            "time",
        ),
    ],
)
def test_dimension_exists(execute_process, data, name, label, dimension_type):
    arguments = {"data": data, "name": name, "label": label, "type": dimension_type}
    with pytest.raises(ProcessParameterInvalid) as ex:
        result = execute_process(arguments)
    assert ex.value.args == (
        "add_dimension",
        "type",
        "Argument must be one of ['spatial', 'temporal', 'bands', 'other'].",
    )
