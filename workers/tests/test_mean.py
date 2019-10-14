import pytest
import sys, os
import xarray as xr
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessArgumentInvalid, ProcessArgumentRequired

FIXTURES_FOLDER = os.path.join(os.path.dirname(__file__), 'fixtures')


@pytest.fixture
def meanEOTask():
    return process.mean.meanEOTask(None, "" , None)


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
def execute_mean_process(generate_data, meanEOTask):
    def wrapped(data_arguments={}, ignore_nodata=None):
        arguments = {}
        if data_arguments is not None: arguments["data"] = generate_data(**data_arguments)
        if ignore_nodata is not None: arguments["ignore_nodata"] = ignore_nodata

        return meanEOTask.process(arguments)
    return wrapped


###################################
# tests:
###################################

@pytest.mark.parametrize('data,expected_result,ignore_nodata', [
    ([1,0,3,2], 1.5, True),
    ([9,2.5,None,-2.5], 3, True),
    ([1,None], None, False),
    ([], None, True)
])
def test_examples(execute_mean_process, data, expected_result, ignore_nodata):
    """
        Test mean process with examples from https://open-eo.github.io/openeo-api/processreference/#mean
    """
    data_arguments = {"data": data, "as_list": True}
    result = execute_mean_process(data_arguments, ignore_nodata=ignore_nodata)
    assert result == expected_result


@pytest.mark.parametrize('data,expected_data,expected_dims,attrs', [
    ([[[[0.2,0.8]]]], [[[0.5]]], ('t','y','x'), {'reduce_by': ['band']}),
    ([[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]], [[[0.125,0.175],[0.075,-0.425]]], ('t','y','x'), {'reduce_by': ['band']}),
    ([[[[0.2,0.8]]]], [[[0.2,0.8]]], ('t','x','band'), {'reduce_by': ['y']}),
    ([[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]], [[[0.075,0.125],[-0.375,0.125]]], ('t','x','band'), {'reduce_by': ['y']}),
])
def test_with_xarray(execute_mean_process, generate_data, data, expected_data, expected_dims, attrs):
    """
        Test mean process with xarray.DataArrays
    """
    expected_result = generate_data(data=expected_data, dims=expected_dims, attrs=attrs)
    result = execute_mean_process({"data": data, "attrs": attrs})
    xr.testing.assert_allclose(result, expected_result)


@pytest.mark.parametrize('data,expected_data,expected_dims,attrs,ignore_nodata', [
    ([[[[np.nan, 0.15], [0.15, 0.2]], [[0.05, np.nan], [-0.9, 0.05]]]], [[[0.05,0.15],[-0.375,0.125]]], ('t','x','band'), {'reduce_by': ['y']}, True),
    ([[[[np.nan, 0.15], [0.15, 0.2]], [[0.05, np.nan], [-0.9, 0.05]]]], [[[np.nan,np.nan],[-0.375,0.125]]], ('t','x','band'), {'reduce_by': ['y']}, False),
])
def test_with_xarray(execute_mean_process, generate_data, data, expected_data, expected_dims, attrs, ignore_nodata):
    """
        Test mean process with xarray.DataArrays with null in data
    """
    expected_result = generate_data(data=expected_data, dims=expected_dims, attrs=attrs)
    result = execute_mean_process({"data": data, "attrs": attrs}, ignore_nodata=ignore_nodata)
    xr.testing.assert_allclose(result, expected_result)