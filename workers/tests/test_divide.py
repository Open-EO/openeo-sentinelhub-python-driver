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
            attrs ={"test_keep_attrs": 42},
            as_list = False
        ):
        if as_list:
            return data

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

        return process.divide.divideEOTask(None, "" , None).process(arguments)
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
