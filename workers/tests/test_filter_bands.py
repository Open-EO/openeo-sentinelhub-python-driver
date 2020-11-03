import pytest
import sys, os
import xarray as xr
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import process
from process._common import ProcessArgumentRequired, ProcessParameterInvalid, Band

FIXTURES_FOLDER = os.path.join(os.path.dirname(__file__), "fixtures")


###################################
# fixtures:
###################################


@pytest.fixture
def filter_bandsEOTask():
    return process.filter_bands.filter_bandsEOTask(None, "", None, {}, "node1", {})


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "data,bands,wavelengths,expected_result",
    [
        # We must temporarily disable these two tests, because we don't know the dimension type unless
        # we have at least one coord in it. This should be fixed.
        #
        # # if no bands are found (using band names), return an empty cube:
        # (
        #     xr.DataArray(
        #         [[[2, 3]]],
        #         dims=("y", "x", "b"),
        #         coords={
        #             "b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842)],
        #         },
        #     ),
        #     ["does_not_exist"],
        #     None,
        #     xr.DataArray(
        #         [[[]]],
        #         dims=("y", "x", "b"),
        #         coords={"b": []},
        #     ),
        # ),
        # # if no bands are found (using wavelengths), return an empty cube:
        # (
        #     xr.DataArray(
        #         [[[2, 3]]],
        #         dims=("y", "x", "b"),
        #         coords={
        #             "b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842)],
        #         },
        #     ),
        #     None,
        #     [[0.0001, 0.0002]],
        #     xr.DataArray(
        #         [[[]]],
        #         dims=("y", "x", "b"),
        #         coords={"b": []},
        #     ),
        # ),
        # find one band:
        (
            xr.DataArray(
                [[[2, 3, 4]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842), Band("B11", None, 1.11)],
                },
            ),
            ["B08"],
            None,
            xr.DataArray(
                [[[3]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B08", "nir", 0.842)],
                },
            ),
        ),
        # find one band by alias:
        (
            xr.DataArray(
                [[[2, 3, 4]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842), Band("B11", None, 1.11)],
                },
            ),
            ["nir"],
            None,
            xr.DataArray(
                [[[3]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B08", "nir", 0.842)],
                },
            ),
        ),
        # find one band by wavelengths:
        (
            xr.DataArray(
                [[[2, 3, 4]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842), Band("B11", None, 1.11)],
                },
            ),
            None,
            [[0.7, 0.9]],
            xr.DataArray(
                [[[3]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B08", "nir", 0.842)],
                },
            ),
        ),
        # multiple filters match, use their ordering:
        (
            xr.DataArray(
                [[[2, 3, 4]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842), Band("B11", None, 1.11)],
                },
            ),
            ["B11", "B08", "B04"],
            None,
            xr.DataArray(
                [[[4, 3, 2]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B11", None, 1.11), Band("B08", "nir", 0.842), Band("B04", "red", 0.665)],
                },
            ),
        ),
        # keep original ordering when a filter matches multiple bands:
        (
            xr.DataArray(
                [[[2, 3, 4]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842), Band("B11", None, 1.11)],
                },
            ),
            None,
            [[1.0, 1.2], [0.0, 0.9]],
            xr.DataArray(
                [[[4, 2, 3]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B11", None, 1.11), Band("B04", "red", 0.665), Band("B08", "nir", 0.842)],
                },
            ),
        ),
        # overlapping filters must not duplicate bands:
        (
            xr.DataArray(
                [[[2, 3, 4]]],
                dims=("y", "x", "band"),
                coords={
                    "band": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842), Band("B11", None, 1.11)],
                },
            ),
            ["B04", "B08", "red"],
            [[0.6, 0.7]],
            xr.DataArray(
                [[[2, 3]]],
                dims=("y", "x", "band"),
                coords={
                    "band": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842)],
                },
            ),
        ),
        # make sure we are handling cubes dimensions correctly by using cube 1x3x2x4:
        (
            xr.DataArray(
                [
                    [[2, 3, 4, 6], [5, 6, 7, 6]],
                    [[1, 2, 3, 6], [4, 5, 6, 6]],
                    [[8, 9, 0, 6], [1, 2, 3, 6]],
                ],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842), Band("B11", None, 1.11), Band("B22")],
                },
            ),
            ["B08"],
            None,
            xr.DataArray(
                [
                    [[3], [6]],
                    [[2], [5]],
                    [[9], [2]],
                ],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B08", "nir", 0.842)],
                },
            ),
        ),
    ],
)
def test_correct(filter_bandsEOTask, data, bands, wavelengths, expected_result):
    """
    Test filter_bands process with correct parameters
    """
    arguments = {
        "data": data,
    }
    if bands is not None:
        arguments["bands"] = bands
    if wavelengths is not None:
        arguments["wavelengths"] = wavelengths
    result = filter_bandsEOTask.process(arguments)
    xr.testing.assert_allclose(result, expected_result)


@pytest.mark.parametrize(
    "bands,wavelengths,expected_exc_param,expected_exc_msg",
    [
        (
            None,
            None,
            "bands/wavelengths",
            "One of the filtering parameters must be specified (BandFilterParameterMissing).",
        ),
        (
            "B01",
            None,
            "bands",
            "Argument must be of types '[array]'.",
        ),
        (
            [42],
            None,
            "bands",
            "Band names must be strings.",
        ),
        (
            None,
            ["Aa"],
            "bands",
            "Wavelengths must be lists with exactly 2 parameters.",
        ),
        (
            None,
            [["Aa"]],
            "bands",
            "Wavelengths must be lists with exactly 2 parameters.",
        ),
        (
            None,
            [["Aa", 3]],
            "bands",
            "Wavelength limits must be numbers.",
        ),
        (
            None,
            [[0.5, 0.3]],
            "bands",
            "First wavelength (min) must be lower or equal to the second one (max).",
        ),
    ],
)
def test_exceptions(filter_bandsEOTask, bands, wavelengths, expected_exc_param, expected_exc_msg):
    data = xr.DataArray(
        [[[2, 3]]],
        dims=("y", "x", "b"),
        coords={"b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842)]},
    )
    arguments = {
        "data": data,
    }
    if bands is not None:
        arguments["bands"] = bands
    if wavelengths is not None:
        arguments["wavelengths"] = wavelengths

    with pytest.raises(ProcessParameterInvalid) as ex:
        result = filter_bandsEOTask.process(arguments)

    assert ex.value.args == ("filter_bands", expected_exc_param, expected_exc_msg)


@pytest.mark.parametrize(
    "data,expected_exc_param,expected_exc_msg",
    [
        # Currently we can't have a datacube which has two dims of type "bands", because of the
        # conflicting names (we should fix this). This is the closest we can get at this time:
        (
            xr.DataArray(
                [[[[2, 3]]]],
                dims=("y", "x", "b2", "b"),
                coords={
                    "b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842)],
                    "b2": [Band("B22")],
                },
            ),
            "data",
            "Multiple dimensions of type 'bands' found.",
        ),
        (
            xr.DataArray(
                [[2, 3]],
                dims=("y", "x"),
            ),
            "data",
            "No dimension of type 'bands' found (DimensionMissing).",
        ),
    ],
)
def test_exceptions_with_wrong_data(filter_bandsEOTask, data, expected_exc_param, expected_exc_msg):
    arguments = {
        "data": data,
        "bands": ["B04"],
    }

    with pytest.raises(ProcessParameterInvalid) as ex:
        result = filter_bandsEOTask.process(arguments)

    assert ex.value.args == ("filter_bands", expected_exc_param, expected_exc_msg)
