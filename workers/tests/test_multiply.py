import math
import os
import sys

import numpy as np
import pytest
import xarray as xr

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessParameterInvalid, DataCube, DimensionType, assert_equal


@pytest.fixture
def execute_multiply_process():
    def wrapped(arguments):
        return process.multiply.multiplyEOTask(None, "", None, {}, "node1", {}).process(arguments)

    return wrapped


def number_as_xarray(value):
    return DataCube(
        [np.nan if value is None else value],
        dim_types={"x": DimensionType.SPATIAL},
        attrs={"simulated_datatype": (float,)},
    )


def list_as_xarray(values):
    return DataCube(
        [np.nan if v is None else v for v in values],
        dim_types={"x": DimensionType.SPATIAL},
        attrs={"simulated_datatype": (float,)},
    )


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "x,y,expected_result",
    [
        (5, 2.5, 12.5),  # example from: https://processes.openeo.org/#multiply
        (-2, -4, 8),  # example from: https://processes.openeo.org/#multiply
        (1, None, None),  # example from: https://processes.openeo.org/#multiply
        # null is returned if any element is no-data:
        (None, 1, None),
        (None, None, None),
    ],
)
def test_correct(execute_multiply_process, x, y, expected_result):
    """
    Test multiply process with examples from https://processes.openeo.org/#multiply
    """
    # No matter which test parameters we get (x, t, expected_result), we would like to test
    # all of the combinations:
    #  - (5, 2.5, 2)
    #  - (number_as_xarray(5), 2.5, number_as_xarray(2))
    #  - (5, number_as_xarray(2.5), number_as_xarray(2))
    #  - (number_as_xarray(5), number_as_xarray(2.5), number_as_xarray(2))
    parameters_forms = [
        (
            x,
            y,
            expected_result,
        ),
        (
            number_as_xarray(x),
            y,
            number_as_xarray(expected_result),
        ),
        (
            x,
            number_as_xarray(y),
            number_as_xarray(expected_result),
        ),
        (
            number_as_xarray(x),
            number_as_xarray(y),
            number_as_xarray(expected_result),
        ),
    ]
    for x, y, expected_result in parameters_forms:
        arguments = {"x": x, "y": y}
        result = execute_multiply_process(arguments)
        if isinstance(expected_result, xr.DataArray):
            assert_equal(result, expected_result)
        else:
            assert result == expected_result


@pytest.mark.parametrize(
    "x,y,expected_result",
    [
        (list_as_xarray([1, 2, 3, 1000, np.nan]), 0.5, list_as_xarray([0.5, 1.0, 1.5, 500, np.nan])),
    ],
)
def test_xarray(execute_multiply_process, x, y, expected_result):
    arguments = {"x": x, "y": y}
    result = execute_multiply_process(arguments)
    assert_equal(result, expected_result)


def test_exception(execute_multiply_process):
    arguments = {
        "x": list_as_xarray([1, 2, 3, 1000, np.nan]),
        "y": list_as_xarray([1]),
    }
    with pytest.raises(ProcessParameterInvalid) as ex:
        result = execute_multiply_process(arguments)
    assert ex.value.args[0] == "multiply"
    assert ex.value.args[1] == "x/y"
