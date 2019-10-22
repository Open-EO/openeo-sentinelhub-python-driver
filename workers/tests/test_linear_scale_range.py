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
            as_number = False
        ):
        if as_number:
            return data

        xrdata = xr.DataArray(
            data,
            dims=dims,
            attrs=attrs,
        )
        return xrdata
    return _construct


@pytest.fixture
def execute_linear_scale_range_process(generate_data):
    def wrapped(data_arguments={}, inputMin=None, inputMax=None, outputMin=None, outputMax=None):
        arguments = {}
        if data_arguments is not None: arguments["x"] = generate_data(**data_arguments)
        if inputMin is not None: arguments["inputMin"] = inputMin
        if inputMax is not None: arguments["inputMax"] = inputMax
        if outputMin is not None: arguments["outputMin"] = outputMin
        if outputMax is not None: arguments["outputMax"] = outputMax

        return process.linear_scale_range.linear_scale_rangeEOTask(None, "" , None).process(arguments)
    return wrapped


###################################
# tests:
###################################

@pytest.mark.parametrize('x,scale_arguments,expected_result', [
    (0.3, {"inputMin":-1, "inputMax":1, "outputMin":0, "outputMax":255}, 165.75),
    (25.5, {"inputMin":0, "inputMax":255}, 0.1),
    (None, {"inputMin":0, "inputMax":100}, None),
])
def test_examples(execute_linear_scale_range_process, x, scale_arguments, expected_result):
    """
        Test linear_scale_range process with examples from https://open-eo.github.io/openeo-api/processreference/#linear_scale_range
    """
    data_arguments = {"data": x, "as_number": True}
    result = execute_linear_scale_range_process(data_arguments, **scale_arguments)
    assert result == expected_result


@pytest.mark.parametrize('x,scale_arguments,expected_data', [
    ([[[[0.2,0.8]]]], {"inputMin":0.2, "inputMax":0.8}, [[[[0.0,1.0]]]]),
    ([[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]], {"inputMin":-1, "inputMax":1, "outputMax": 10}, [[[[5.5, 5.75], [5.75, 6]], [[5.25, 5.5], [0.5, 5.25]]]]),
    ([[[[8]]]], {"inputMin":0, "inputMax":10, "outputMin":0, "outputMax":255},[[[[204]]]]),
])
def test_with_xarray(execute_linear_scale_range_process, generate_data, x, scale_arguments, expected_data):
    """
        Test linear_scale_range process with xarray.DataArrays
    """
    expected_result = generate_data(data=expected_data)
    result = execute_linear_scale_range_process({"data": x}, **scale_arguments)
    xr.testing.assert_allclose(result, expected_result)


@pytest.mark.parametrize('x,scale_arguments,expected_data', [
    ([[[[np.nan,0.8]]]], {"inputMin":0.2, "inputMax":0.8}, [[[[np.nan,1.0]]]]),
    ([[[[0.1, 0.15], [0.15, 0.2]], [[np.nan, np.nan], [-0.9, np.nan]]]], {"inputMin":-1, "inputMax":1, "outputMax": 10}, [[[[5.5, 5.75], [5.75, 6]], [[np.nan, np.nan], [0.5, np.nan]]]]),
    ([[[[np.nan]]]], {"inputMin":0, "inputMax":10, "outputMin":0, "outputMax":255},[[[[np.nan]]]]),
])
def test_with_xarray_nulls(execute_linear_scale_range_process, generate_data, x, scale_arguments, expected_data):
    """
        Test linear_scale_range process with xarray.DataArrays with null in data
    """
    expected_result = generate_data(data=expected_data)
    result = execute_linear_scale_range_process({"data": x}, **scale_arguments)
    xr.testing.assert_allclose(result, expected_result)