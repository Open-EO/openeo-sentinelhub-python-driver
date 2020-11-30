import math
import os
import sys

import numpy as np
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessParameterInvalid, DataCube, DimensionType, assert_equal


@pytest.fixture
def execute_normalized_difference_process():
    def wrapped(arguments):
        return process.normalized_difference.normalized_differenceEOTask(None, "", None, {}, "node1", {}).process(
            arguments
        )

    return wrapped


def number_as_xarray(value):
    return DataCube(
        [np.nan if value is None else value],
        dims=("x"),
        dim_types={"x": DimensionType.SPATIAL},
        attrs={"simulated_datatype": (float,)},
    )


def list_as_xarray(values):
    return DataCube(
        [np.nan if v is None else v for v in values],
        dims=("x"),
        dim_types={"x": DimensionType.SPATIAL},
        attrs={"simulated_datatype": (float,)},
    )


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "x,y,expected_result",
    [
        (5, 2.5, 2.5 / 7.5),
        (-2, -4, -2 / 6),
        # null is returned if any element is no-data:
        (1, None, None),
        (None, 1, None),
        (None, None, None),
    ],
)
def test_correct(execute_normalized_difference_process, x, y, expected_result):
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
        result = execute_normalized_difference_process(arguments)
        if isinstance(expected_result, DataCube):
            assert_equal(result, expected_result)
        else:
            assert result == expected_result


@pytest.mark.parametrize(
    "x,y,expected_result",
    [
        (
            list_as_xarray([1, 2, 3, 1000, np.nan]),
            0.2,
            list_as_xarray([0.8 / 1.2, 1.8 / 2.2, 2.8 / 3.2, 999.8 / 1000.2, np.nan]),
        ),
    ],
)
def test_xarray(execute_normalized_difference_process, x, y, expected_result):
    arguments = {"x": x, "y": y}
    result = execute_normalized_difference_process(arguments)
    assert_equal(result, expected_result)


def test_exception(execute_normalized_difference_process):
    arguments = {
        "x": list_as_xarray([1, 2, 3, 1000, np.nan]),
        "y": list_as_xarray([1]),
    }
    with pytest.raises(ProcessParameterInvalid) as ex:
        result = execute_normalized_difference_process(arguments)
    assert ex.value.args[0] == "normalized_difference"
    assert ex.value.args[1] == "x/y"
