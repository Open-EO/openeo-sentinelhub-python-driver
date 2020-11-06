import math
import numpy as np
import os
import pytest
import sys
import xarray as xr

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessParameterInvalid, DataCube


@pytest.fixture
def execute_add_process():
    def wrapped(arguments):
        return process.add.addEOTask(None, "", None, {}, "node1", {}).process(arguments)

    return wrapped


###################################
# tests:
###################################


def list_as_xarray(values):
    return DataCube([np.nan if v is None else v for v in values], attrs={"simulated_datatype": (float,)})


@pytest.mark.parametrize(
    "x,y,expected_result",
    [
        (5, 2.5, 7.5),  # example from: https://processes.openeo.org/#add
        (-2, -4, -6),  # example from: https://processes.openeo.org/#add
        # null is returned if any element is no-data:
        (1, None, None),  # example from: https://processes.openeo.org/#add
        (None, 1, None),
        (None, None, None),
        (math.inf, 1, math.inf),
        (math.inf, None, None),
    ],
)
def test_examples(execute_add_process, x, y, expected_result):
    arguments = {"x": x, "y": y}
    result = execute_add_process(arguments)
    assert result == expected_result


@pytest.mark.parametrize(
    "x,y,expected_result",
    [
        (list_as_xarray([1, -2, 0, 1.5, np.nan]), 1, list_as_xarray([2, -1, 1, 2.5, np.nan])),
        (1, list_as_xarray([1, -2, 0, 1.5, np.nan]), list_as_xarray([2, -1, 1, 2.5, np.nan])),
        (list_as_xarray([1, -2, 0, 1.5, np.nan]), np.nan, list_as_xarray([np.nan, np.nan, np.nan, np.nan, np.nan])),
        (np.nan, list_as_xarray([1, -2, 0, 1.5, np.nan]), list_as_xarray([np.nan, np.nan, np.nan, np.nan, np.nan])),
        (
            list_as_xarray([1, -2, 0, 1.5, np.nan]),
            list_as_xarray([1, -1.5, 0, np.nan, 1]),
            list_as_xarray([2, -3.5, 0, np.nan, np.nan]),
        ),
    ],
)
def test_xarray(execute_add_process, x, y, expected_result):
    arguments = {"x": x, "y": y}
    result = execute_add_process(arguments)
    xr.testing.assert_allclose(result, expected_result)


@pytest.mark.parametrize(
    "x,y,expected_result",
    [
        (list_as_xarray([1, -2, 0, 1.5, np.nan]), list_as_xarray([]), list_as_xarray([2, -1, 1, 2.5, np.nan])),
        (list_as_xarray([1, -2, 0, 1.5, np.nan]), list_as_xarray([1]), list_as_xarray([2, -1, 1, 2.5, np.nan])),
        (
            list_as_xarray([1, -2, 0, 1.5, np.nan]),
            list_as_xarray([1, -1.5, 0, 3, 4, 5, 6, 7]),
            list_as_xarray([2, -3.5, 0, np.nan, np.nan]),
        ),
    ],
)
def test_array_different_dimensions(execute_add_process, x, y, expected_result):
    arguments = {"x": x, "y": y}
    with pytest.raises(ProcessParameterInvalid) as ex:
        result = execute_add_process(arguments)
    assert ex.value.args[0] == "add"
    assert ex.value.args[1] == "x/y"
