import pytest
import sys, os
import xarray as xr
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import process
from process._common import ProcessArgumentRequired, ProcessParameterInvalid

FIXTURES_FOLDER = os.path.join(os.path.dirname(__file__), "fixtures")


###################################
# fixtures:
###################################


@pytest.fixture
def construct_data():
    def _construct(data, bands, dims=("y", "x", "band"), band_aliases={"nir": "B08", "red": "B04"}):
        xrdata = xr.DataArray(
            np.array(data, dtype=np.float),
            dims=dims,
            coords={
                "band": bands,
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
    synthetic_data = [[[2, 3]]]
    bands = ["B04", "B08"]
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
    return process.ndvi.ndviEOTask(None, "", None, {}, "node1", {})


###################################
# tests:
###################################


def test_correct(ndviEOTask, data1, actual_result1):
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


def test_name(ndviEOTask, data1, actual_result2):
    """
    Test ndvi process name parameter
    """
    arguments = {"data": data1, "name": "test_name01"}
    result = ndviEOTask.process(arguments)

    assert result == actual_result2

    arguments = {"data": data1, "name": "...wrong///"}
    with pytest.raises(ProcessParameterInvalid) as ex:
        result = ndviEOTask.process(arguments)
    assert ex.value.args == ("ndvi", "name", "String does not match the required pattern.")


@pytest.mark.parametrize(
    "data,bands,expected_data,expected_bands",
    [
        (
            [[[[0.25, 0.15], [0.15, 0.25]], [[0.58, 0.22], [None, None]]]],
            ["B08", "B04"],
            [[[[0.25], [-0.25]], [[0.45], [None]]]],
            ["ndvi"],
        ),
    ],
)
def test_multidim(ndviEOTask, construct_data, data, bands, expected_data, expected_bands):
    """
    Test ndvi process with data where multiple dimensions have length > 1
    """
    arguments = {"data": construct_data(data, bands, dims=("t", "y", "x", "band"))}
    result = ndviEOTask.process(arguments)
    expected_result = construct_data(expected_data, expected_bands, dims=("t", "y", "x", "band"))
    xr.testing.assert_allclose(result, expected_result)
