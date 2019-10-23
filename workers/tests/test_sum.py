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
def execute_sum_process(generate_data):
    def wrapped(data_arguments={}, ignore_nodata=None):
        arguments = {}
        if data_arguments is not None: arguments["data"] = generate_data(**data_arguments)
        if ignore_nodata is not None: arguments["ignore_nodata"] = ignore_nodata

        return process.sum.sumEOTask(None, "" , None).process(arguments)
    return wrapped


###################################
# tests:
###################################

@pytest.mark.parametrize('data,ignore_nodata,expected_result', [
    ([5,1], True, 6),
    ([-2,4,2.5], True, 4.5),
    ([1,None], False, None)
])
def test_examples(execute_sum_process, data, expected_result, ignore_nodata):
    """
        Test sum process with examples from https://open-eo.github.io/openeo-api/processreference/#sum
    """
    data_arguments = {"data": data, "as_list": True}
    result = execute_sum_process(data_arguments, ignore_nodata=ignore_nodata)
    assert result == expected_result


@pytest.mark.parametrize('array1,array2,expected_data', [
    ([[[[0.2,0.8]]]], [[[[0.2,0.8]]]], [[[[0.4,1.6]]]]),
])
def test_with_xarray(execute_sum_process, generate_data, array1, array2, expected_data):
    """
        Test mean process with xarray.DataArrays
    """
    expected_result = generate_data(data=[expected_data])[0]
    result = execute_sum_process({"data": (array1,array2)})
    xr.testing.assert_allclose(result, expected_result)


@pytest.mark.parametrize('array1,array2,ignore_nodata,expected_data', [
    ([[[[np.nan,np.nan]]]], [[[[0.2,np.nan]]]], True, [[[[0.2,0.0]]]]),
    ([[[[np.nan,np.nan]]]], [[[[0.2,np.nan]]]], False, [[[[np.nan,np.nan]]]]),
])
def test_with_xarray(execute_sum_process, generate_data, array1, array2, expected_data, ignore_nodata):
    """
        Test mean process with xarray.DataArrays with null in data
    """
    expected_result = generate_data(data=[expected_data])[0]
    result = execute_sum_process({"data": (array1,array2)}, ignore_nodata=ignore_nodata)
    xr.testing.assert_allclose(result, expected_result)