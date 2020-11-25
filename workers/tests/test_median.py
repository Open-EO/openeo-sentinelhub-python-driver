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
def execute_median_process(generate_data):
    def wrapped(data_arguments={}, ignore_nodata=None):
        arguments = {}
        if data_arguments is not None:
            arguments["data"] = generate_data(**data_arguments)
        if ignore_nodata is not None:
            arguments["ignore_nodata"] = ignore_nodata

        return process.median.medianEOTask(None, "", None, {}, "node1", {}).process(arguments)

    return wrapped


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "data,ignore_nodata,expected_result",
    [
        ([1, 3, 3, 6, 7, 8, 9], True, 6),
        ([1, 2, 3, 4, 5, 6, 8, 9], True, 4.5),
        ([-1, -0.5, None, 1], True, -0.5),
        ([-1, 0, None, 1], False, None),
    ],
)
def test_examples(execute_median_process, data, expected_result, ignore_nodata):
    """
    Test median process with examples from https://open-eo.github.io/openeo-api/processreference/#median
    """
    data_arguments = {"data": data, "as_list": True}
    result = execute_median_process(data_arguments, ignore_nodata=ignore_nodata)
    assert result == expected_result


@pytest.mark.parametrize(
    "data,attrs,expected_dims,expected_data",
    [
        ([[[[0.2, 0.8]]]], {"reduce_by": ["band"]}, ("t", "y", "x"), [[[0.5]]]),
        (
            [[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]],
            {"reduce_by": ["band"]},
            ("t", "y", "x"),
            [[[0.125, 0.175], [0.075, -0.425]]],
        ),
        ([[[[0.2, 0.8]]]], {"reduce_by": ["y"]}, ("t", "x", "band"), [[[0.2, 0.8]]]),
        (
            [[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]], [[0.2, 0.05], [-0.15, 0.1]]]],
            {"reduce_by": ["y"]},
            ("t", "x", "band"),
            [[[0.1, 0.1], [-0.15, 0.1]]],
        ),
    ],
)
def test_with_xarray(execute_median_process, generate_data, data, expected_data, expected_dims, attrs):
    """
    Test median process with xarray.DataArrays
    """
    expected_result = generate_data(data=expected_data, dims=expected_dims, attrs=attrs)
    result = execute_median_process({"data": data, "attrs": attrs})
    assert_equal(result, expected_result)


@pytest.mark.parametrize(
    "data,attrs,ignore_nodata,expected_dims,expected_data",
    [
        (
            [[[[np.nan, 0.15], [0.15, 0.2]], [[0.05, np.nan], [-0.9, 0.05]]]],
            {"reduce_by": ["y"]},
            True,
            ("t", "x", "band"),
            [[[0.05, 0.15], [-0.375, 0.125]]],
        ),
        (
            [[[[np.nan, 0.15], [0.15, 0.2]], [[0.05, np.nan], [-0.9, 0.05]]]],
            {"reduce_by": ["y"]},
            False,
            ("t", "x", "band"),
            [[[np.nan, np.nan], [-0.375, 0.125]]],
        ),
    ],
)
def test_with_xarray_nulls(
    execute_median_process, generate_data, data, expected_data, expected_dims, attrs, ignore_nodata
):
    """
    Test median process with xarray.DataArrays with null in data
    """
    expected_result = generate_data(data=expected_data, dims=expected_dims, attrs=attrs)
    result = execute_median_process({"data": data, "attrs": attrs}, ignore_nodata=ignore_nodata)
    assert_equal(result, expected_result)
