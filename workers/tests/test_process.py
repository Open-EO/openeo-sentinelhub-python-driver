import logging
import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessParameterInvalid, DataCube, assert_equal


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "arguments,param,required,allowed_types,default_value,expected_result,expected_exception,expected_exc_args",
    [
        ({}, "x", False, [float, type(None)], None, None, None, None),
        ({"x": 123}, "x", False, [float, type(None)], None, 123.0, None, None),
        ({"x": None}, "x", False, [float, type(None)], 11, None, None, None),
        (
            {"x": "whatever"},
            "x",
            False,
            [float],
            11,
            None,
            ProcessParameterInvalid,
            ("Process", "x", "Argument must be of types '[number]'."),
        ),
        (
            {"x": "whatever"},
            "x",
            False,
            [int],
            11,
            None,
            ProcessParameterInvalid,
            ("Process", "x", "Argument must be of types '[integer]'."),
        ),
        (
            {"x": "whatever"},
            "x",
            False,
            [DataCube],
            11,
            None,
            ProcessParameterInvalid,
            ("Process", "x", "Argument must be of types '[raster-cube]'."),
        ),
        (
            {"x": DataCube([[1, 2]], dims=("x", "y"))},
            "x",
            False,
            [DataCube],
            11,
            DataCube([[1, 2]], dims=("x", "y")),
            None,
            None,
        ),
        (
            {"x": DataCube([[1, 2]], dims=("x", "y"), attrs={"simulated_datatype": (float,)})},
            "x",
            False,
            [DataCube],
            11,
            None,
            ProcessParameterInvalid,
            ("Process", "x", "Argument must be of types '[raster-cube]'."),
        ),
    ],
)
def test_validate_parameter(
    arguments, param, required, allowed_types, default_value, expected_result, expected_exception, expected_exc_args
):
    """
    Test ProcessEOTask.validate_parameter() method
    """

    node = process._common.ProcessEOTask(None, "", None, {}, "node1", {})

    if expected_exception is not None:
        with pytest.raises(expected_exception) as ex:
            node.validate_parameter(arguments, param, required, allowed_types, default_value)
        assert ex.value.args == expected_exc_args
    else:
        result = node.validate_parameter(arguments, param, required, allowed_types, default_value)
        # checking the result depends on the result data type:
        if isinstance(result, DataCube):
            assert_equal(result, expected_result)
        else:
            assert result == expected_result
