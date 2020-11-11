import pytest
import sys, os
import xarray as xr
import numpy as np
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import Band


@pytest.fixture
def execute_eq_process():
    def wrapped(x, y, delta=None, case_sensitive=None):
        arguments = {"x": x, "y": y}
        if delta is not None:
            arguments["delta"] = delta
        if case_sensitive is not None:
            arguments["case_sensitive"] = case_sensitive
        return process.eq.eqEOTask(None, "", None, {}, "node1", {}).process(arguments)

    return wrapped


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "x,y,delta,case_sensitive,expected_result",
    [
        (1, None, None, None, None),
        (None, None, None, None, None),
        (1, 1, None, None, True),
        (1, "1", None, None, False),
        (0, False, None, None, False),
        (1.02, 1, 0.01, None, False),
        (-1, -1.001, 0.01, None, True),
        (115, 110, 10, None, True),
        ("Test", "test", None, None, False),
        ("Test", "test", None, False, True),
        ("Ä", "ä", None, False, True),
        # ("00:00:00+00:00", "00:00:00Z", None, None, True),
        # ("2018-01-01T12:00:00Z", "2018-01-01T12:00:00", None, None, False),
        # ("2018-01-01T00:00:00Z", "2018-01-01T01:00:00+01:00", None, None, True),
        ([1, 2, 3], [1, 2, 3], None, None, False),
    ],
)
def test_examples(execute_eq_process, x, y, delta, case_sensitive, expected_result):
    """
    Test eq process with examples from https://processes.openeo.org/1.0.0/#eq
    """
    result = execute_eq_process(x, y, delta, case_sensitive)
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
                [[[[False, True]]], [[[False, False]]], [[[True, False]]]],
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
                [[[[False, None]]], [[[False, True]]], [[[None, False]]]],
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
                [[[[False, np.nan]]], [[[False, False]]], [[[np.nan, True]]]],
                attrs={"simulated_datatype": (float,)},
            ),
        ),
        (
            xr.DataArray(
                [[1, 2], [3, 4]],
                dims=("a", "b"),
                attrs={"simulated_datatype": (float,)},
            ),
            xr.DataArray(
                [[1, 3], [2, 4]],
                dims=("b", "a"),
                attrs={"simulated_datatype": (float,)},
            ),
            xr.DataArray(
                [[True, True], [True, True]],
                dims=("a", "b"),
                attrs={"simulated_datatype": (float,)},
            ),
        ),
    ],
)
def test_with_two_xarrays(execute_eq_process, x, y, expected_result):
    """
    Test eq process with xarray.DataArrays
    """
    result = execute_eq_process(x, y)
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
                [[[[False, False]]], [[[False, True]]], [[[True, False]]]],
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
            [],
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
def test_with_xarray_and_scalar(execute_eq_process, x, y, expected_result):
    """
    Test eq process with xarray.DataArrays
    """
    result = execute_eq_process(x, y)
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
                [[[[True, True]]], [[[False, True]]], [[[True, False]]]],
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
                [[[[True, None]]], [[[False, True]]], [[[None, False]]]],
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
                [[[[False, np.nan]]], [[[False, False]]], [[[np.nan, True]]]],
                attrs={"simulated_datatype": (float,), "reduce_by": []},
            ),
        ),
    ],
)
def test_with_xarrays_and_delta(execute_eq_process, x, y, delta, expected_result):
    """
    Test eq process with xarray.DataArrays
    """
    result = execute_eq_process(x, y, delta=delta)
    # assert_identical also matches attrs
    xr.testing.assert_identical(result, expected_result)
