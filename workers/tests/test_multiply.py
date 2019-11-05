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
            xrdata = xr.DataArray(d, dims=dims, attrs=attrs)
            data_list.append(xrdata)

        return data_list
    return _construct


@pytest.fixture
def execute_multiply_process(generate_data):
    def wrapped(data_arguments={}, ignore_nodata=None):
        arguments = {}
        if data_arguments is not None: arguments["data"] = generate_data(**data_arguments)
        if ignore_nodata is not None: arguments["ignore_nodata"] = ignore_nodata

        return process.multiply.multiplyEOTask(None, "" , None).process(arguments)
    return wrapped


###################################
# tests:
###################################

@pytest.mark.parametrize('data,ignore_nodata,expected_result', [
    ([5,0], True, 0),
    ([-2,4,2.5], True, -20),
    ([1,None], False, None)
])
def test_examples(execute_multiply_process, data, expected_result, ignore_nodata):
    """
        Test multiply process with examples from https://open-eo.github.io/openeo-api/processreference/#multiply
    """
    data_arguments = {"data": data, "as_list": True}
    result = execute_multiply_process(data_arguments, ignore_nodata=ignore_nodata)
    assert result == expected_result


@pytest.mark.parametrize('array1,array2,expected_data', [
    ([[[[0.2,0.8]]]], [[[[0.2,0.8]]]], [[[[0.04,0.64]]]]),
])
def test_with_xarray(execute_multiply_process, generate_data, array1, array2, expected_data):
    """
        Test multiply process with xarray.DataArrays
    """
    expected_result = generate_data(data=[expected_data])[0]
    result = execute_multiply_process({"data": (array1,array2)})
    xr.testing.assert_allclose(result, expected_result)


@pytest.mark.parametrize('array1,array2,ignore_nodata,expected_data', [
    ([[[[np.nan,0.0]]]], [[[[0.2,np.nan]]]], True, [[[[0.2,0.0]]]]),
    ([[[[np.nan,np.nan]]]], [[[[0.2,np.nan]]]], False, [[[[np.nan,np.nan]]]]),
    ([[[[2.0, 1.0]]]], [[[[0.2, np.nan]]]], False, [[[[0.4, np.nan]]]]),
])
def test_with_xarray_nulls(execute_multiply_process, generate_data, array1, array2, expected_data, ignore_nodata):
    """
        Test multiply process with xarray.DataArrays with null in data
    """
    expected_result = generate_data(data=[expected_data])[0]
    result = execute_multiply_process({"data": (array1,array2)}, ignore_nodata=ignore_nodata)
    xr.testing.assert_allclose(result, expected_result)


@pytest.mark.parametrize('array1,array2,expected_data', [
    ([[[[0.2,0.8]]]], [[[[0.2,0.8]]]], [[[[0.04,0.64]]]]),
])
def test_product(generate_data, array1, array2, expected_data):
    """
        Test product process, which is an alias of multiply
    """
    expected_result = generate_data(data=[expected_data])[0]
    arguments = ({"data": generate_data(data=[array1,array2])})
    result = process.product.productEOTask(None, "", None).process(arguments)
    xr.testing.assert_allclose(result, expected_result)


@pytest.mark.parametrize('data,reduce_by,expected_data,expected_dims', [
    ([[[[0.2,0.8]]],[[[1.0,2.0]]]], 't', [[[0.2,1.6]]], ('y','x','band')),
])
def test_xarray_directly(execute_multiply_process, generate_data, data, reduce_by, expected_data, expected_dims):
    """
        Test multiply process by passing a DataArray to be reduced directly (instead of a list)
    """
    expected_result = generate_data(data=expected_data, dims=expected_dims, attrs={"reduce_by": reduce_by}, as_dataarray=True)
    result = execute_multiply_process({"data": data, "attrs": {"reduce_by": reduce_by}, "as_dataarray": True})
    xr.testing.assert_allclose(result, expected_result)