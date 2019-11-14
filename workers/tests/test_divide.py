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
            data = ([[[[0.2,0.8]]]], [[[[0.2,0.8]]]]),
            attrs = {"test_keep_attrs": 42},
            dims = ('t','y','x','band'),
            as_list = False,
            as_dataarray = False,
        ):
        if as_list:
            return data

        if as_dataarray:
            return xr.DataArray(data, dims=dims, attrs=attrs)

        data_list = []

        for d in data:
            xrdata = xr.DataArray(d)
            data_list.append(xrdata)

        return data_list
    return _construct


@pytest.fixture
def execute_divide_process(generate_data):
    def wrapped(data_arguments={}, ignore_nodata=None):
        arguments = {}
        if data_arguments is not None: arguments["data"] = generate_data(**data_arguments)
        if ignore_nodata is not None: arguments["ignore_nodata"] = ignore_nodata

        return process.divide.divideEOTask(None, "" , None, {}, "node1").process(arguments)
    return wrapped


###################################
# tests:
###################################

@pytest.mark.parametrize('data,ignore_nodata,expected_result', [
    ([15,5], True, 3),
    ([-2,4,2.5], True, -0.2),
    ([1,None], False, None)
])
def test_examples(execute_divide_process, data, expected_result, ignore_nodata):
    """
        Test divide process with examples from https://open-eo.github.io/openeo-api/processreference/#divide
    """
    data_arguments = {"data": data, "as_list": True}
    result = execute_divide_process(data_arguments, ignore_nodata=ignore_nodata)
    assert result == expected_result


@pytest.mark.parametrize('array1,array2,expected_data', [
    ([[[[0.2,0.8]]]], [[[[-0.2,4]]]], [[[[-1.0,0.2]]]]),
])
def test_with_xarray(execute_divide_process, generate_data, array1, array2, expected_data):
    """
        Test divide process with xarray.DataArrays
    """
    expected_result = generate_data(data=[expected_data])[0]
    result = execute_divide_process({"data": (array1,array2)})
    xr.testing.assert_allclose(result, expected_result)


@pytest.mark.parametrize('array1,array2,ignore_nodata,expected_data', [
    ([[[[np.nan,0.0]]]], [[[[0.2,np.nan]]]], True, [[[[5.0,0.0]]]]),
    ([[[[np.nan,0.0]]]], [[[[0.2,np.nan]]]], False, [[[[np.nan,np.nan]]]]),
    ([[[[2.0, 1.0]]]], [[[[0.2, np.nan]]]], False, [[[[10.0, np.nan]]]]),
])
def test_with_xarray_nulls(execute_divide_process, generate_data, array1, array2, expected_data, ignore_nodata):
    """
        Test divide process with xarray.DataArrays with null in data
    """
    expected_result = generate_data(data=[expected_data])[0]
    result = execute_divide_process({"data": (array1,array2)}, ignore_nodata=ignore_nodata)
    xr.testing.assert_allclose(result, expected_result)


@pytest.mark.parametrize('data,reduce_by,expected_data,expected_dims', [
    ([[[[0.2,0.8]]],[[[0.2,2.0]]]], 't', [[[1.0,0.4]]], ('y','x','band')),
])
def test_xarray_directly(execute_divide_process, generate_data, data, reduce_by, expected_data, expected_dims):
    """
        Test divide process by passing a DataArray to be reduced directly (instead of a list)
    """
    expected_result = generate_data(data=expected_data, dims=expected_dims, attrs={"reduce_by": reduce_by}, as_dataarray=True)
    result = execute_divide_process({"data": data, "attrs": {"reduce_by": reduce_by}, "as_dataarray": True})
    xr.testing.assert_allclose(result, expected_result)


@pytest.mark.parametrize('number1,number2,arr1,arr2,expected_data,num_first', [
    (1000, 0.1, [[[[1.0,2.0]]],[[[4.0,5.0]]]], [[[[20.0,10.0]]],[[[5.0,4.0]]]], [[[[500,500]]],[[[500,500]]]], True),
    (2, 0.05, [[[[1.0,2.0]]],[[[4.0,5.0]]]], [[[[20.0,10.0]]],[[[5.0,4.0]]]], [[[[0.5,2.0]]],[[[8.0,12.5]]]], False),
])
def test_with_numbers(execute_divide_process, generate_data, number1, number2, arr1, arr2, expected_data, num_first):
    """
        Test divide process by a list of numbers and DataArrays
    """
    expected_result = generate_data(data=expected_data, as_dataarray=True)
    arr1 = generate_data(data=arr1, as_dataarray=True)
    arr2 = generate_data(data=arr2, as_dataarray=True)

    if num_first:
        data = [number1, arr1, number2, arr2]
    else:
        data = [arr1, number1, arr2, number2]

    result = execute_divide_process({"data": data, "as_list": True})
    xr.testing.assert_allclose(result, expected_result)