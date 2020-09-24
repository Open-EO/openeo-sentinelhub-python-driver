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
            data = [[[[0.2,0.8]]]],
            dims = ('t','y','x','band'),
            attrs = {'reduce_by': ['band']},
            as_list = False
        ):
        if as_list:
            return data

        xrdata = xr.DataArray(
            data,
            dims=dims,
            attrs=attrs,
        )
        return xrdata
    return _construct


@pytest.fixture
def execute_max_process(generate_data):
    def wrapped(data_arguments={}, ignore_nodata=None):
        arguments = {}
        if data_arguments is not None: arguments["data"] = generate_data(**data_arguments)
        if ignore_nodata is not None: arguments["ignore_nodata"] = ignore_nodata

        return process.max.maxEOTask(None, "" , None, {}, "node1", {}).process(arguments)
    return wrapped


###################################
# tests:
###################################

@pytest.mark.parametrize('data,ignore_nodata,expected_result', [
    ([1,0,3,2], True, 3),
    ([5,2.5,None,-0.7], True, 5),
    ([1,0,3,None,2], False, None),
    ([], True, None)
])
def test_examples(execute_max_process, data, expected_result, ignore_nodata):
    """
        Test max process with examples from https://open-eo.github.io/openeo-api/processreference/#max
    """
    data_arguments = {"data": data, "as_list": True}
    result = execute_max_process(data_arguments, ignore_nodata=ignore_nodata)
    assert result == expected_result


@pytest.mark.parametrize('data,attrs,expected_dims,expected_data', [
    ([[[[0.2,0.8]]]], {'reduce_by': ['band']}, ('t','y','x'), [[[0.8]]]),
    ([[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]], {'reduce_by': ['band']}, ('t','y','x'), [[[0.15, 0.2], [0.1, 0.05]]]),
    ([[[[0.2,0.8]]]], {'reduce_by': ['y']}, ('t','x','band'), [[[0.2,0.8]]]),
    ([[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]], {'reduce_by': ['y']}, ('t','x','band'), [[[0.1, 0.15], [0.15, 0.2]]]),
])
def test_with_xarray(execute_max_process, generate_data, data, expected_data, expected_dims, attrs):
    """
        Test max process with xarray.DataArrays
    """
    expected_result = generate_data(data=expected_data, dims=expected_dims, attrs=attrs)
    result = execute_max_process({"data": data, "attrs": attrs})
    xr.testing.assert_allclose(result, expected_result)


@pytest.mark.parametrize('data,attrs,ignore_nodata,expected_dims,expected_data', [
    ([[[[np.nan, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, np.nan]]]], {'reduce_by': ['band']}, True, ('t','y','x'), [[[0.15, 0.2], [0.1, -0.9]]]),
    ([[[[np.nan, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, np.nan]]]], {'reduce_by': ['band']}, False, ('t','y','x'), [[[np.nan, 0.2], [0.1, np.nan]]])
])
def test_with_xarray_nulls(execute_max_process, generate_data, data, expected_data, expected_dims, attrs, ignore_nodata):
    """
        Test max process with xarray.DataArrays with null in data
    """
    expected_result = generate_data(data=expected_data, dims=expected_dims, attrs=attrs)
    result = execute_max_process({"data": data, "attrs": attrs}, ignore_nodata=ignore_nodata)
    xr.testing.assert_allclose(result, expected_result)
