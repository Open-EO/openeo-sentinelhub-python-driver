import pytest
import sys, os
import xarray as xr
import numpy as np
import pandas as pd
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process


@pytest.fixture
def execute_subtract_process():
    def wrapped(x, y):
        return process.subtract.subtractEOTask(None, "", None, {}, "node1", {}).process({"x": x, "y": y})

    return wrapped


###################################
# tests:
###################################


@pytest.mark.parametrize("x,y,expected_result", [(5, 2.5, 2.5), (-2, 4, -6), (1, None, None)])
def test_examples(execute_subtract_process, x, y, expected_result):
    """
    Test subtract process with examples from https://processes.openeo.org/1.0.0/#subtract
    """
    result = execute_subtract_process(x, y)
    assert result == expected_result


@pytest.mark.parametrize(
    "x,y,expected_result",
    [
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    ),
                },
                attrs={"simulated_datatype": (float,)},
            ),
            0.2,
            xr.DataArray(
                [[[[0, 0.6]]], [[[0.7, 0.1]]], [[[0.3, 0.3]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    ),
                },
                attrs={"simulated_datatype": (float,)},
            ),
        ),
        (
            0.2,
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    ),
                },
                attrs={"simulated_datatype": (float,)},
            ),
            xr.DataArray(
                [[[[0, -0.6]]], [[[-0.7, -0.1]]], [[[-0.3, -0.3]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    ),
                },
                attrs={"simulated_datatype": (float,)},
            ),
        ),
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    ),
                },
                attrs={"simulated_datatype": (float,)},
            ),
            None,
            xr.DataArray(
                [[[[np.nan, np.nan]]], [[[np.nan, np.nan]]], [[[np.nan, np.nan]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    ),
                },
                attrs={"simulated_datatype": (float,)},
            ),
        ),
        (
            None,
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    ),
                },
                attrs={"simulated_datatype": (float,)},
            ),
            xr.DataArray(
                [[[[np.nan, np.nan]]], [[[np.nan, np.nan]]], [[[np.nan, np.nan]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    ),
                },
                attrs={"simulated_datatype": (float,)},
            ),
        ),
    ],
)
def test_with_xarray_and_number(execute_subtract_process, x, y, expected_result):
    """
    Test subtract process with xarray.DataArrays
    """
    result = execute_subtract_process(x, y)
    xr.testing.assert_allclose(result, expected_result)


@pytest.mark.parametrize(
    "x,y,expected_result",
    [
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    ),
                },
                attrs={"simulated_datatype": (float,)},
            ),
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    ),
                },
                attrs={"simulated_datatype": (float,)},
            ),
            xr.DataArray(
                [[[[0, 0]]], [[[0, 0]]], [[[0, 0]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    ),
                },
                attrs={"simulated_datatype": (float,)},
            ),
        ),
        (
            xr.DataArray(
                [[[[0.9, 42]]], [[[1.3, 14]]], [[[88, 0.7]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    ),
                },
                attrs={"simulated_datatype": (float,)},
            ),
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    ),
                },
                attrs={"simulated_datatype": (float,)},
            ),
            xr.DataArray(
                [[[[0.7, 41.2]]], [[[0.4, 13.7]]], [[[87.5, 0.2]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    ),
                },
                attrs={"simulated_datatype": (float,)},
            ),
        ),
    ],
)
def test_with_two_xarrays(execute_subtract_process, x, y, expected_result):
    """
    Test subtract process with xarray.DataArrays
    """
    result = execute_subtract_process(x, y)
    xr.testing.assert_allclose(result, expected_result)
