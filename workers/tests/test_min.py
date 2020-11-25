import pytest
import sys, os
import xarray as xr
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import DataCube, DimensionType, assert_equal


@pytest.fixture
def generate_data():
    def _construct(
        data=[[[[0.2, 0.8]]]],
        dims=("t", "y", "x", "band"),
        attrs={"reduce_by": ["band"]},
        dim_types={
            "x": DimensionType.SPATIAL,
            "y": DimensionType.SPATIAL,
            "t": DimensionType.TEMPORAL,
            "band": DimensionType.BANDS,
        },
        as_list=False,
    ):
        if as_list:
            return data

        xrdata = DataCube(
            data,
            dims=dims,
            attrs=attrs,
        )
        return xrdata

    return _construct


@pytest.fixture
def execute_min_process(generate_data):
    def wrapped(data_arguments={}, ignore_nodata=None):
        arguments = {}
        if data_arguments is not None:
            arguments["data"] = generate_data(**data_arguments)
        if ignore_nodata is not None:
            arguments["ignore_nodata"] = ignore_nodata

        return process.min.minEOTask(None, "", None, {}, "node1", {}).process(arguments)

    return wrapped


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "data,ignore_nodata,expected_result",
    [([1, 0, 3, 2], True, 0), ([5, 2.5, None, -0.7], True, -0.7), ([1, 0, 3, None, 2], False, None), ([], True, None)],
)
def test_examples(execute_min_process, data, expected_result, ignore_nodata):
    """
    Test min process with examples from https://open-eo.github.io/openeo-api/processreference/#min
    """
    data_arguments = {"data": data, "as_list": True}
    result = execute_min_process(data_arguments, ignore_nodata=ignore_nodata)
    assert result == expected_result


@pytest.mark.parametrize(
    "data,attrs,expected_dims,expected_data",
    [
        ([[[[0.2, 0.8]]]], {"reduce_by": ["band"]}, ("t", "y", "x"), [[[0.2]]]),
        (
            [[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]],
            {"reduce_by": ["band"]},
            ("t", "y", "x"),
            [[[0.1, 0.15], [0.05, -0.9]]],
        ),
        ([[[[0.2, 0.8]]]], {"reduce_by": ["y"]}, ("t", "x", "band"), [[[0.2, 0.8]]]),
        (
            [[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]],
            {"reduce_by": ["y"]},
            ("t", "x", "band"),
            [[[0.05, 0.1], [-0.9, 0.05]]],
        ),
    ],
)
def test_with_xarray(execute_min_process, generate_data, data, expected_data, expected_dims, attrs):
    """
    Test min process with xarray.DataArrays
    """
    expected_result = generate_data(data=expected_data, dims=expected_dims, attrs=attrs)
    result = execute_min_process({"data": data, "attrs": attrs})
    assert_equal(result, expected_result)


@pytest.mark.parametrize(
    "data,attrs,ignore_nodata,expected_dims,expected_data",
    [
        (
            [[[[np.nan, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, np.nan]]]],
            {"reduce_by": ["band"]},
            True,
            ("t", "y", "x"),
            [[[0.15, 0.15], [0.05, -0.9]]],
        ),
        (
            [[[[np.nan, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, np.nan]]]],
            {"reduce_by": ["band"]},
            False,
            ("t", "y", "x"),
            [[[np.nan, 0.15], [0.05, np.nan]]],
        ),
    ],
)
def test_with_xarray_nulls(
    execute_min_process, generate_data, data, expected_data, expected_dims, attrs, ignore_nodata
):
    """
    Test min process with xarray.DataArrays with null in data
    """
    expected_result = generate_data(data=expected_data, dims=expected_dims, attrs=attrs)
    result = execute_min_process({"data": data, "attrs": attrs}, ignore_nodata=ignore_nodata)
    assert_equal(result, expected_result)
