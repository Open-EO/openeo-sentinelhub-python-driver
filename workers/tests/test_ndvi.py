import pytest
import sys, os
import xarray as xr

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import process
from process._common import ProcessArgumentRequired, ProcessArgumentInvalid

FIXTURES_FOLDER = os.path.join(os.path.dirname(__file__), 'fixtures')


###################################
# fixtures:
###################################


@pytest.fixture
def construct_data():
    def _construct(data, bands, dims=('y', 'x', 'band'), band_aliases={"nir": "B08","red": "B04"}):
        xrdata = xr.DataArray(
            data,
            dims=dims,
            coords={
                'band': bands,
            },
            attrs={
                "band_aliases": band_aliases,
                "bbox": "",
            },
        )
        return xrdata
    return _construct


@pytest.fixture
def data1(construct_data):
    synthetic_data = [[[2,3]]]
    bands = ["B04","B08"]
    return construct_data(synthetic_data, bands)
    


@pytest.fixture
def actual_result1(construct_data):
    synthetic_data = [[[0.2]]]   
    bands = ["ndvi"]
    return construct_data(synthetic_data, bands)


@pytest.fixture
def actual_result2(construct_data):
    synthetic_data = [[[0.2]]]   
    bands = ["test_name01"]
    return construct_data(synthetic_data, bands)


@pytest.fixture
def ndviEOTask():
    return process.ndvi.ndviEOTask(None, "", None)


###################################
# tests:
###################################


def test_correct(ndviEOTask,data1, actual_result1):
    """
        Test ndvi process with correct parameters
    """
    arguments = {"data": data1}
    result = ndviEOTask.process(arguments)
    assert result == actual_result1


def test_missing_data(ndviEOTask):
    """
        Test ndvi process with empty arguments
    """
    with pytest.raises(ProcessArgumentRequired) as ex:
        result = ndviEOTask.process({})
    
    assert ex.value.args[0] == "Process 'ndvi' requires argument 'data'."


def test_name(ndviEOTask,data1,actual_result2):
    """
        Test ndvi process name parameter
    """
    arguments = {"data": data1,"name": "test_name01"}
    result = ndviEOTask.process(arguments)

    assert result == actual_result2

    arguments = {"data": data1,"name": "...wrong///"}
    with pytest.raises(ProcessArgumentInvalid) as ex:
        result = ndviEOTask.process(arguments)

    assert ex.value.args[0] == "The argument 'name' in process 'ndvi' is invalid: string does not match the required pattern."