import pytest
import sys, os
import xarray as xr
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessArgumentInvalid, ProcessArgumentRequired


@pytest.fixture
def generate_data():
    def _construct(
        data=[[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]],
        dims=("t", "y", "x", "band"),
        reduce_by="band",
        as_list=False,
    ):
        if as_list:
            return data

        xrdata = xr.DataArray(
            data,
            dims=dims,
            attrs={"reduce_by": [reduce_by]},
        )
        return xrdata

    return _construct


@pytest.fixture
def execute_array_element_process(generate_data):
    def wrapped(data_arguments={}, index=None, return_nodata=None):
        arguments = {}
        if data_arguments is not None:
            arguments["data"] = generate_data(**data_arguments)
        if index is not None:
            arguments["index"] = index
        if return_nodata is not None:
            arguments["return_nodata"] = return_nodata

        return process.array_element.array_elementEOTask(None, "", None, {}, "arrayel1", {}).process(arguments)

    return wrapped


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "data,return_nodata,index,expected_result",
    [([9, 8, 7, 6, 5], None, 2, 7), (["A", "B", "C"], None, 0, "A"), ([], True, 0, None)],
)
def test_examples(execute_array_element_process, data, index, return_nodata, expected_result):
    """
    Test array_element process with examples from https://open-eo.github.io/openeo-api/processreference/#array_element
    """
    data_arguments = {"data": data, "as_list": True}
    result = execute_array_element_process(data_arguments=data_arguments, index=index, return_nodata=return_nodata)
    assert result == expected_result


@pytest.mark.parametrize(
    "data,index,reduce_by,expected_data,expected_dims",
    [
        (
            [[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]],
            0,
            "band",
            [[[0.1, 0.15], [0.05, -0.9]]],
            ("t", "y", "x"),
        ),
        (
            [[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]],
            1,
            "y",
            [[[0.05, 0.1], [-0.9, 0.05]]],
            ("t", "x", "band"),
        ),
    ],
)
def test_with_xarray(
    execute_array_element_process, generate_data, data, index, reduce_by, expected_data, expected_dims
):
    """
    Test array_element process with xarray.DataArrays
    """
    expected_result = generate_data(data=expected_data, dims=expected_dims, reduce_by=reduce_by)
    result = execute_array_element_process(data_arguments={"data": data, "reduce_by": reduce_by}, index=index)
    xr.testing.assert_allclose(result, expected_result)


def test_with_xarray_out_bounds(execute_array_element_process, generate_data):
    """
    Test array_element process with xarray.DataArrays with out of bounds index
    """
    with pytest.raises(ProcessArgumentInvalid) as ex:
        result = execute_array_element_process(index=5)
    assert ex.value.args[0] == "The argument 'index' in process 'array_element' is invalid: Index out of bounds."


@pytest.mark.parametrize(
    "data_arguments,index,expected_data,expected_dims",
    [
        ({}, 5, [[[np.nan, np.nan], [np.nan, np.nan]]], ("t", "y", "x")),
    ],
)
def test_with_xarray_out_bounds_return_nodata(
    execute_array_element_process, generate_data, data_arguments, index, expected_data, expected_dims
):
    """
    Test array_element process with xarray.DataArrays with out of bounds index and return_no_data
    """
    expected_result = generate_data(expected_data, dims=expected_dims)
    result = execute_array_element_process(data_arguments=data_arguments, index=index, return_nodata=True)
    xr.testing.assert_equal(result, expected_result)
