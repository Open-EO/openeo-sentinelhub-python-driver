import pytest
import sys, os
import xarray as xr
import numpy as np
import pandas as pd

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


@pytest.mark.parametrize(
    "data,nir,red,target_band,expected_result",
    [
        (
            xr.DataArray(
                [[[2, 3]]],
                dims=("y", "x", "band"),
                coords={
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    )
                },
            ),
            None,
            None,
            None,
            xr.DataArray([[0.2]], dims=("y", "x")),
        ),
        (
            xr.DataArray(
                [[[2, 3]]],
                dims=("y", "x", "band"),
                coords={
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    )
                },
            ),
            None,
            None,
            "my_ndvi",
            xr.DataArray(
                [[[2, 3, 0.2]]],
                dims=("y", "x", "band"),
                coords={
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08", "my_ndvi"], ["red", "nir", None], [0.665, 0.842, None]],
                        names=("_name", "_alias", "_wavelength"),
                    )
                },
            ),
        ),
        (
            xr.DataArray(
                [[[2, 3]]],
                dims=("y", "x", "band"),
                coords={
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    )
                },
            ),
            "nir",
            "red",
            None,
            xr.DataArray([[0.2]], dims=("y", "x")),
        ),
        (
            xr.DataArray(
                [[[2, 3]]],
                dims=("y", "x", "band"),
                coords={
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    )
                },
            ),
            "red",  # switch
            "nir",
            None,
            xr.DataArray([[-0.2]], dims=("y", "x")),
        ),
        (
            xr.DataArray(
                [[[2, 3]]],
                dims=("y", "x", "band"),
                coords={
                    "band": pd.MultiIndex.from_arrays(
                        [["B01", "B02"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    )
                },
            ),
            "B01",  # band names instead of aliases (switched)
            "B02",
            None,
            xr.DataArray([[-0.2]], dims=("y", "x")),
        ),
    ],
)
def test_correct(ndviEOTask, data, nir, red, target_band, expected_result):
    """
    Test ndvi process with correct parameters
    """
    arguments = {
        "data": data,
        "target_band": target_band,
    }
    if nir is not None:
        arguments["nir"] = nir
    if red is not None:
        arguments["red"] = red
    result = ndviEOTask.process(arguments)
    # `assert_allclose` fails when comparing the MultiIndexes, even when they are the
    # same; instead, `assert_equal` works:
    xr.testing.assert_equal(result, expected_result)


@pytest.mark.parametrize(
    "data,nir,red,target_band,expected_exc_param,expected_exc_msg",
    [
        (
            xr.DataArray([[2, 3]], dims=("y", "x")),
            None,
            None,
            None,
            "data",
            "Dimension 'band' is missing (DimensionAmbiguous).",
        ),
        (
            xr.DataArray([[[2, 3]]], dims=("y", "x", "band")),
            None,
            None,
            None,
            "data",
            "Dimension 'band' does not contain bands (DimensionAmbiguous).",
        ),
        (
            xr.DataArray(
                [[[2, 3]]],
                dims=("y", "x", "band"),
                coords={
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], [None, None], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    )
                },
            ),
            None,
            None,
            None,
            "nir",
            "Parameter does not match any band (NirBandAmbiguous).",
        ),
        (
            xr.DataArray(
                [[[2, 3]]],
                dims=("y", "x", "band"),
                coords={
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["nir", None], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    )
                },
            ),
            None,
            None,
            None,
            "red",
            "Parameter does not match any band (RedBandAmbiguous).",
        ),
        (
            xr.DataArray(
                [[[2, 3, 11]]],
                dims=("y", "x", "band"),
                coords={
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08", "B11"], ["nir", "red", None], [0.665, 0.842, 0.999]],
                        names=("_name", "_alias", "_wavelength"),
                    )
                },
            ),
            None,
            None,
            "B11",
            "target_band",
            "Band name already exists (BandExists).",
        ),
        (
            xr.DataArray(
                [[[2, 3, 11]]],
                dims=("y", "x", "band"),
                coords={
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08", "B11"], ["nir", "red", "B11alias"], [0.665, 0.842, 0.999]],
                        names=("_name", "_alias", "_wavelength"),
                    )
                },
            ),
            None,
            None,
            "B11alias",
            "target_band",
            "Band name already exists (BandExists).",
        ),
        (
            xr.DataArray(
                [[[2, 3]]],
                dims=("y", "x", "band"),
                coords={
                    "band": pd.MultiIndex.from_arrays(
                        [["B04", "B08"], ["nir", "red"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
                    )
                },
            ),
            None,
            None,
            "...wrong///",
            "target_band",
            "String does not match the required pattern.",
        ),
    ],
)
def test_exceptions(ndviEOTask, data, nir, red, target_band, expected_exc_param, expected_exc_msg):
    """
    Test ndvi process throws exceptions
    """
    arguments = {
        "data": data,
        "target_band": target_band,
    }
    if nir is not None:
        arguments["nir"] = nir
    if red is not None:
        arguments["red"] = red
    with pytest.raises(ProcessParameterInvalid) as ex:
        result = ndviEOTask.process(arguments)
    assert ex.value.args == ("ndvi", expected_exc_param, expected_exc_msg)


def test_missing_data(ndviEOTask):
    """
    Test ndvi process with empty arguments
    """
    with pytest.raises(ProcessArgumentRequired) as ex:
        result = ndviEOTask.process({})

    assert ex.value.args[0] == "Process 'ndvi' requires argument 'data'."
