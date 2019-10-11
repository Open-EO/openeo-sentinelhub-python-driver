import pytest
import sys, os
import xarray as xr

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessArgumentInvalid, ProcessArgumentRequired

FIXTURES_FOLDER = os.path.join(os.path.dirname(__file__), 'fixtures')


@pytest.fixture
def sumEOTask():
    return process.sum.sumEOTask(None, "" , None)


@pytest.fixture
def generate_data():
    def _construct(
            data = ([[[[0.2,0.8]]]], [[[[0.2,0.8]]]]),
            dims = ('t','y', 'x', 'band'),
            attrs = {'reduce_by': ['band']},
            as_list = False
        ):
        if as_list:
            return data[0]

        data_list = []

        for d in data:
            xrdata = xr.DataArray(
                d,
                dims=dims,
                attrs=attrs,
            )
            data_list.append(xrdata)

        return data_list
    return _construct


@pytest.fixture
def execute_sum_process(generate_data, sumEOTask):
    def wrapped(data_arguments={}, ignore_nodata=None):
        arguments = {}
        if data_arguments is not None: arguments["data"] = generate_data(**data_arguments)
        if ignore_nodata is not None: arguments["ignore_nodata"] = ignore_nodata

        return sumEOTask.process(arguments)
    return wrapped


###################################
# tests:
###################################

@pytest.mark.parametrize('data,expected_result,ignore_nodata', [
    ([5,1], 6, True),
    ([-2,4,2.5], 4.5, True),
    ([1,None], None, False)
])
def test_examples(execute_sum_process, data, expected_result, ignore_nodata):
    """
        Test sum process with examples from https://open-eo.github.io/openeo-api/processreference/#sum
    """
    data_arguments = {"data": data, "as_list": True}
    result = execute_sum_process(data_arguments, ignore_nodata=ignore_nodata)

    assert result == expected_result


def test_with_xarray(execute_sum_process, generate_data):
    """
        Test sum process with xarray.DataArrays as we typically use it
    """
    expected_result = generate_data(data=([[[[0.4,0.16]]]]))[0]
    result = execute_sum_process()

    xr.testing.assert_allclose(result, expected_result)