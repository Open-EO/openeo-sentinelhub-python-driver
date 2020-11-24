import pytest
import sys, os
import xarray as xr
import numpy as np
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessParameterInvalid, Band


@pytest.fixture
def execute_mask_process():
    def wrapped(data, mask, replacement=None):
        arguments = {"data": data, "mask": mask}
        if replacement is not None:
            arguments["replacement"] = replacement
        return process.mask.maskEOTask(None, "", None, {}, "node1", {}).process(arguments)

    return wrapped


###################################
# tests:###################################


@pytest.mark.parametrize(
    "data,mask,replacement,expected_result",
    [
        (
            xr.DataArray([[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.3, 0.5]]]], dims=("x", "y", "t", "b")),
            xr.DataArray([[[[True, False]]], [[[False, True]]], [[[False, False]]]], dims=("x", "y", "t", "b")),
            None,
            xr.DataArray([[[[np.nan, 0.8]]], [[[0.9, np.nan]]], [[[0.3, 0.5]]]], dims=("x", "y", "t", "b")),
        ),
        (
            xr.DataArray([[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.3, 0.5]]]], dims=("x", "y", "t", "b")),
            xr.DataArray([[[[True, False]]], [[[False, True]]], [[[False, False]]]], dims=("x", "y", "t", "b")),
            False,
            xr.DataArray([[[[False, 0.8]]], [[[0.9, False]]], [[[0.3, 0.5]]]], dims=("x", "y", "t", "b")),
        ),
        (
            xr.DataArray([[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.3, 0.5]]]], dims=("x", "y", "t", "b")),
            xr.DataArray([True, False], dims=("b")),
            False,
            xr.DataArray([[[[False, 0.8]]], [[[False, 0.3]]], [[[False, 0.5]]]], dims=("x", "y", "t", "b")),
        ),
        (
            xr.DataArray([[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.3, 0.5]]]], dims=("x", "y", "t", "b")),
            xr.DataArray([[True, False], [False, False], [True, True]], dims=("x", "b")),
            -999,
            xr.DataArray([[[[-999, 0.8]]], [[[0.9, 0.3]]], [[[-999, -999]]]], dims=("x", "y", "t", "b")),
        ),
        (
            xr.DataArray([[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.3, 0.5]]]], dims=("x", "y", "t", "b")),
            xr.DataArray([[True, False, True], [False, False, True]], dims=("b", "x")),
            -999,
            xr.DataArray([[[[-999, 0.8]]], [[[0.9, 0.3]]], [[[-999, -999]]]], dims=("x", "y", "t", "b")),
        ),
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.3, 0.5]]]],
                dims=("x", "y", "t", "b"),
                coords={"b": [Band("B01"), Band("B02")], "x": [5, 6, 7], "y": [11]},
            ),
            xr.DataArray(
                [[True, False, True], [False, False, True]],
                dims=("b", "x"),
                coords={"b": [Band("B01"), Band("B02")], "x": [5, 6, 7]},
            ),
            np.inf,
            xr.DataArray(
                [[[[np.inf, 0.8]]], [[[0.9, 0.3]]], [[[np.inf, np.inf]]]],
                dims=("x", "y", "t", "b"),
                coords={"b": [Band("B01"), Band("B02")], "x": [5, 6, 7], "y": [11]},
            ),
        ),
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.3, 0.5]]]],
                dims=("x", "y", "t", "b"),
                coords={"b": [Band("B01"), Band("B02")], "x": [5, 6, 7], "y": [11]},
            ),
            xr.DataArray(
                [[2.1, 0, -0.2], [0, 0, 0.01]],
                dims=("b", "x"),
                coords={"b": [Band("B01"), Band("B02")], "x": [5, 6, 7]},
            ),
            np.inf,
            xr.DataArray(
                [[[[np.inf, 0.8]]], [[[0.9, 0.3]]], [[[np.inf, np.inf]]]],
                dims=("x", "y", "t", "b"),
                coords={"b": [Band("B01"), Band("B02")], "x": [5, 6, 7], "y": [11]},
            ),
        ),
    ],
)
def test_with_two_xarrays(execute_mask_process, data, mask, replacement, expected_result):
    """
    Test mask process with xarray.DataArrays
    """
    result = execute_mask_process(
        data,
        mask,
        replacement,
    )
    xr.testing.assert_allclose(result, expected_result)


@pytest.mark.parametrize(
    "data,mask,expected_error",
    [
        (
            xr.DataArray([[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.3, 0.5]]]], dims=("x", "y", "t", "b")),
            xr.DataArray([[[[True, False]]], [[[False, True]]], [[[False, False]]]], dims=("x", "y", "t", "a")),
            ("mask", "data/mask", "Some dimensions in mask are not available in data."),
        ),
        (
            xr.DataArray([[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.3, 0.5]]]], dims=("x", "y", "t", "b")),
            xr.DataArray([[[[True]]], [[[False]]], [[[False]]]], dims=("x", "y", "t", "b")),
            ("mask", "data/mask", "Data and mask have different labels."),
        ),
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.3, 0.5]]]],
                dims=("x", "y", "t", "b"),
                coords={"b": [Band("B01"), Band("B02")]},
            ),
            xr.DataArray([True, False], dims=("b"), coords={"b": [Band("B02"), Band("B03")]}),
            ("mask", "data/mask", "Data and mask have different labels."),
        ),
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.3, 0.5]]]],
                dims=("x", "y", "t", "b"),
                coords={"b": [Band("B01"), Band("B02")], "x": [0, 1, 2]},
            ),
            xr.DataArray(
                [[True, False], [True, False], [True, False]],
                dims=("x", "b"),
                coords={"b": [Band("B01"), Band("B02")], "x": [0, 1, 3]},
            ),
            ("mask", "data/mask", "Data and mask have different labels."),
        ),
        (
            xr.DataArray([[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.3, 0.5]]]], dims=("x", "y", "t", "b")),
            xr.DataArray(
                [[[[True, True, True]]], [[[False, False, False]]], [[[False, False, False]]]],
                dims=("x", "y", "t", "b"),
            ),
            ("mask", "data/mask", "Data and mask have different labels."),
        ),
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.3, 0.5]]]],
                dims=("x", "y", "t", "b"),
                coords={"b": [Band("B01"), Band("B02")], "x": [0, 1, 2]},
            ),
            xr.DataArray(
                [[True, False], [True, False]],
                dims=("x", "b"),
                coords={"b": [Band("B01"), Band("B02")], "x": [0, 1]},
            ),
            ("mask", "data/mask", "Data and mask have different labels."),
        ),
    ],
)
def test_exception(execute_mask_process, data, mask, expected_error):
    with pytest.raises(ProcessParameterInvalid) as ex:
        result = execute_mask_process(data, mask)
    assert ex.value.args == expected_error
