import math
import os
import sys

import numpy as np
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessParameterInvalid, DataCube, DimensionType, assert_equal


@pytest.fixture
def execute_divide_process():
    def wrapped(arguments):
        return process.divide.divideEOTask(None, "", None, {}, "node1", {}).process(arguments)

    return wrapped


###################################
# tests:
###################################


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


@pytest.mark.parametrize(
    "x,y,expected_result",
    [
        (5, 2.5, 2),  # example from: https://processes.openeo.org/#divide
        (-2, 4, -0.5),  # example from: https://processes.openeo.org/#divide
        (1, None, None),  # example from: https://processes.openeo.org/#divide
        (3, 2, 1.5),  # numbers should always be treated as floats
        # null is returned if any element is no-data:
        (None, 1, None),
        (None, 0, None),
        (None, None, None),
        # The computations follow IEEE Standard 754 whenever the processing environment supports it. Therefore, a division
        # by zero results in ±infinity if the processing environment supports it.
        #   https://en.wikipedia.org/wiki/Division_by_zero#Computer_arithmetic
        #   In IEEE 754 arithmetic, a ÷ +0 is positive infinity when a is positive, negative infinity when a is negative,
        #   and NaN when a = ±0.
        (3, 0, math.inf),
        (-3, 0, -math.inf),
        (0, 0, None),
    ],
)
def test_examples(execute_divide_process, x, y, expected_result):
    """
    Test divide process with examples from https://processes.openeo.org/#divide
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
        result = execute_divide_process(arguments)
        if isinstance(expected_result, DataCube):
            assert_equal(result, expected_result)
        else:
            assert result == expected_result


@pytest.mark.parametrize(
    "x,y,expected_result",
    [
        (list_as_xarray([1, 2, 3, 1000, np.nan]), 2, list_as_xarray([0.5, 1.0, 1.5, 500, np.nan])),
    ],
)
def test_xarray(execute_divide_process, x, y, expected_result):
    arguments = {"x": x, "y": y}
    result = execute_divide_process(arguments)
    assert_equal(result, expected_result)


def test_exception(execute_divide_process):
    arguments = {
        "x": list_as_xarray([1, 2, 3, 1000, np.nan]),
        "y": list_as_xarray([1]),
    }
    with pytest.raises(ProcessParameterInvalid) as ex:
        result = execute_divide_process(arguments)
    assert ex.value.args[0] == "divide"
    assert ex.value.args[1] == "x/y"
