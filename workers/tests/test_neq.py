import pytest
import sys, os
import xarray as xr
import numpy as np
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import Band


@pytest.fixture
def execute_neq_process():
    def wrapped(x, y, delta=None, case_sensitive=None):
        arguments = {"x": x, "y": y}
        if delta is not None:
            arguments["delta"] = delta
        if case_sensitive is not None:
            arguments["case_sensitive"] = case_sensitive
        return process.neq.neqEOTask(None, "", None, {}, "node1", {}).process(arguments)

    return wrapped


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "x,y,delta,case_sensitive,expected_result",
    [
        (1, None, None, None, None),
        (1, 1, None, None, False),
        (1, "1", None, None, True),
        (0, False, None, None, True),
        (1.02, 1, 0.01, None, True),
        (-1, -1.001, 0.01, None, False),
        (115, 110, 10, None, False),
        ("Test", "test", None, None, True),
        ("Test", "test", None, False, False),
        ("Ä", "ä", None, False, False),
        # ("00:00:00+00:00", "00:00:00Z", None, None, True),
        # ("2018-01-01T12:00:00Z", "2018-01-01T12:00:00", None, None, False),
        # ("2018-01-01T00:00:00Z", "2018-01-01T01:00:00+01:00", None, None, True),
        ([1, 2, 3], [1, 2, 3], None, None, False),
    ],
)
def test_examples(execute_neq_process, x, y, delta, case_sensitive, expected_result):
    """
    Test neq process with examples from https://processes.openeo.org/1.0.0/#neq
    """
    result = execute_neq_process(x, y, delta, case_sensitive)
    assert result == expected_result


@pytest.mark.parametrize(
    "x,y,expected_result",
    [
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.3, 0.5]]]],
                attrs={"simulated_datatype": (float,)},
            ),
            xr.DataArray(
                [[[[0, 0.8]]], [[[0.7, 0.1]]], [[[0.3, 0.3]]]],
                attrs={"simulated_datatype": (float,)},
            ),
            xr.DataArray(
                [[[[True, False]]], [[[True, True]]], [[[False, True]]]],
                attrs={"simulated_datatype": (float,)},
            ),
        ),
        (
            xr.DataArray(
                [[[[0.2, None]]], [[[0.9, 0.1]]], [[[None, 0.5]]]],
                attrs={"simulated_datatype": (float,)},
            ),
            xr.DataArray(
                [[[[0, None]]], [[[0.7, 0.1]]], [[[None, 0.3]]]],
                attrs={"simulated_datatype": (float,)},
            ),
            xr.DataArray(
                [[[[True, None]]], [[[True, False]]], [[[None, True]]]],
                attrs={"simulated_datatype": (float,)},
            ),
        ),
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[np.nan, 0.5]]]],
                attrs={"simulated_datatype": (float,)},
            ),
            xr.DataArray(
                [[[[0, np.nan]]], [[[0.7, 0.1]]], [[[0.3, 0.5]]]],
                attrs={"simulated_datatype": (float,)},
            ),
            xr.DataArray(
                [[[[True, np.nan]]], [[[True, True]]], [[[np.nan, False]]]],
                attrs={"simulated_datatype": (float,)},
            ),
        ),
    ],
)
def test_with_two_xarrays(execute_neq_process, x, y, expected_result):
    """
    Test neq process with xarray.DataArrays
    """
    result = execute_neq_process(x, y)
    xr.testing.assert_allclose(result, expected_result)


@pytest.mark.parametrize(
    "x,y,expected_result",
    [
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.3, 0.5]]]],
                attrs={"simulated_datatype": (float,)},
            ),
            0.3,
            xr.DataArray(
                [[[[True, True]]], [[[True, False]]], [[[False, True]]]],
                attrs={"simulated_datatype": (float,)},
            ),
        ),
        (
            xr.DataArray(
                [[[[0.2, None]]], [[[0.9, 0.1]]], [[[None, 0.5]]]],
                attrs={"simulated_datatype": (float,)},
            ),
            None,
            xr.DataArray(
                [[[[None, None]]], [[[None, None]]], [[[None, None]]]],
                attrs={"simulated_datatype": (float,)},
            ),
        ),
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[np.nan, 0.5]]]],
                attrs={"simulated_datatype": (float,)},
            ),
            {},
            xr.DataArray(
                [[[[False, False]]], [[[False, False]]], [[[None, False]]]],
                attrs={"simulated_datatype": (float,)},
            ),
        ),
        (
            xr.DataArray(
                [[[[0, 0.8]]], [[[0.9, 0.3]]], [[[np.nan, 0.5]]]],
                attrs={"simulated_datatype": (float,)},
            ),
            [],
            xr.DataArray(
                [[[[False, False]]], [[[False, False]]], [[[None, False]]]],
                attrs={"simulated_datatype": (float,)},
            ),
        ),
    ],
)
def test_with_xarray_and_scalar(execute_neq_process, x, y, expected_result):
    """
    Test neq process with xarray.DataArrays
    """
    result = execute_neq_process(x, y)
    xr.testing.assert_allclose(result, expected_result)


@pytest.mark.parametrize(
    "x,y,delta,expected_result",
    [
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.3, 0.5001]]]],
                attrs={"simulated_datatype": (float,)},
            ),
            xr.DataArray(
                [[[[0, 0.8]]], [[[0.6, 0.1]]], [[[0.3, 0.3]]]],
                attrs={"simulated_datatype": (float,)},
            ),
            0.2,
            xr.DataArray(
                [[[[False, False]]], [[[True, False]]], [[[False, True]]]],
                attrs={"simulated_datatype": (float,)},
            ),
        ),
        (
            xr.DataArray(
                [[[[0.1, None]]], [[[0.9, 0.1]]], [[[None, 0.5]]]],
                attrs={"simulated_datatype": (float,)},
            ),
            xr.DataArray(
                [[[[0, None]]], [[[0.7, 0.1]]], [[[None, 0.3]]]],
                attrs={"simulated_datatype": (float,)},
            ),
            0.1,
            xr.DataArray(
                [[[[False, None]]], [[[True, False]]], [[[None, True]]]],
                attrs={"simulated_datatype": (float,)},
            ),
        ),
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[np.nan, 0.5]]]],
                attrs={"simulated_datatype": (float,), "reduce_by": []},
            ),
            xr.DataArray(
                [[[[0, np.nan]]], [[[0.7, 0.1]]], [[[0.3, 0.5]]]],
                attrs={"simulated_datatype": (float,), "reduce_by": []},
            ),
            0,
            xr.DataArray(
                [[[[True, np.nan]]], [[[True, True]]], [[[np.nan, False]]]],
                attrs={"simulated_datatype": (float,), "reduce_by": []},
            ),
        ),
    ],
)
def test_with_xarrays_and_delta(execute_neq_process, x, y, delta, expected_result):
    """
    Test neq process with xarray.DataArrays
    """
    result = execute_neq_process(x, y, delta=delta)
    # assert_identical also matches attrs
    xr.testing.assert_identical(result, expected_result)
