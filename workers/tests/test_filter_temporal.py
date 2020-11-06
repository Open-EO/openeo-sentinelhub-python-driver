from datetime import datetime
import os
import sys

import numpy as np
import pytest
import xarray as xr

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessParameterInvalid, DataCube, DimensionType


@pytest.fixture
def execute_process():
    def wrapped(arguments):
        return process.filter_temporal.filter_temporalEOTask(None, "", None, {}, "node1", {}).process(arguments)

    return wrapped


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "extent,expected_dates",
    [
        (
            [None, "2020-01-01"],
            [datetime(2014, 3, 4), datetime(2014, 3, 5), datetime(2014, 3, 6), datetime(2014, 3, 7)],
        ),
        ([None, "2014-03-06"], [datetime(2014, 3, 4), datetime(2014, 3, 5)]),
        ([None, "2014-03-01"], []),
        (
            ["2014-03-01", None],
            [datetime(2014, 3, 4), datetime(2014, 3, 5), datetime(2014, 3, 6), datetime(2014, 3, 7)],
        ),
        (
            ["2014-03-04", None],
            [datetime(2014, 3, 4), datetime(2014, 3, 5), datetime(2014, 3, 6), datetime(2014, 3, 7)],
        ),
        (["2014-03-05", None], [datetime(2014, 3, 5), datetime(2014, 3, 6), datetime(2014, 3, 7)]),
        (["2014-03-07", None], [datetime(2014, 3, 7)]),
        (["2014-03-08", None], []),
    ],
)
def test_date_interval(execute_process, extent, expected_dates):
    dimension = "t"
    data = DataCube(
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
    )
    arguments = {
        "data": data,
        "extent": extent,
        "dimension": dimension,
    }
    result = execute_process(arguments)
    expected_dates_np = [np.datetime64(x) for x in expected_dates]
    assert list(result.coords["t"].values) == expected_dates_np


@pytest.mark.parametrize(
    "dimension",
    [
        ("t",),
        (None,),
    ],
)
def test_dimension(execute_process, dimension):
    dimension = "t"
    data = DataCube(
        [[1, 2, 3, 4], [5, 6, 7, 8]],
        dims=["x", "t"],
        coords={
            "x": [1000, 2000],
            "t": [
                datetime(2014, 3, 4),
                datetime(2014, 3, 5),
                datetime(2014, 3, 6),
                datetime(2014, 3, 7),
            ],
        },
        dim_types={"t": DimensionType.TEMPORAL, "x": DimensionType.SPATIAL},
    )
    extent = [None, "2014-03-06"]
    arguments = {
        "data": data,
        "extent": extent,
        "dimension": dimension,
    }
    result = execute_process(arguments)
    expected_dates_np = [np.datetime64(x) for x in [datetime(2014, 3, 4), datetime(2014, 3, 5)]]
    assert list(result.coords["t"].values) == expected_dates_np
