import pytest
import sys, os
import xarray as xr
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import process
from process._common import (
    ProcessArgumentRequired,
    ProcessParameterInvalid,
    Band,
    DataCube,
    DimensionType,
    assert_equal,
)

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
        # if no bands are found (using band names), return an empty cube:
        (
            DataCube(
                [[[2, 3]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842)],
                },
                dim_types={"b": DimensionType.BANDS},
            ),
            ["does_not_exist"],
            None,
            DataCube(
                [[[]]],
                dims=("y", "x", "b"),
                coords={"b": []},
                dim_types={"b": DimensionType.BANDS},
            ),
        ),
        # # if no bands are found (using wavelengths), return an empty cube:
        (
            DataCube(
                [[[2, 3]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842)],
                },
                dim_types={"b": DimensionType.BANDS},
            ),
            None,
            [[0.0001, 0.0002]],
            DataCube(
                [[[]]],
                dims=("y", "x", "b"),
                coords={"b": []},
                dim_types={"b": DimensionType.BANDS},
            ),
        ),
        # find one band:
        (
            DataCube(
                [[[2, 3, 4]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842), Band("B11", None, 1.11)],
                },
                dim_types={"b": DimensionType.BANDS},
            ),
            ["B08"],
            None,
            DataCube(
                [[[3]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B08", "nir", 0.842)],
                },
                dim_types={"b": DimensionType.BANDS},
            ),
        ),
        # find one band by alias:
        (
            DataCube(
                [[[2, 3, 4]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842), Band("B11", None, 1.11)],
                },
                dim_types={"b": DimensionType.BANDS},
            ),
            ["nir"],
            None,
            DataCube(
                [[[3]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B08", "nir", 0.842)],
                },
                dim_types={"b": DimensionType.BANDS},
            ),
        ),
        # find one band by wavelengths:
        (
            DataCube(
                [[[2, 3, 4]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842), Band("B11", None, 1.11)],
                },
                dim_types={"b": DimensionType.BANDS},
            ),
            None,
            [[0.7, 0.9]],
            DataCube(
                [[[3]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B08", "nir", 0.842)],
                },
                dim_types={"b": DimensionType.BANDS},
            ),
        ),
        # multiple filters match, use their ordering:
        (
            DataCube(
                [[[2, 3, 4]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842), Band("B11", None, 1.11)],
                },
                dim_types={"b": DimensionType.BANDS},
            ),
            ["B11", "B08", "B04"],
            None,
            DataCube(
                [[[4, 3, 2]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B11", None, 1.11), Band("B08", "nir", 0.842), Band("B04", "red", 0.665)],
                },
                dim_types={"b": DimensionType.BANDS},
            ),
        ),
        # keep original ordering when a filter matches multiple bands:
        (
            DataCube(
                [[[2, 3, 4]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842), Band("B11", None, 1.11)],
                },
                dim_types={"b": DimensionType.BANDS},
            ),
            None,
            [[1.0, 1.2], [0.0, 0.9]],
            DataCube(
                [[[4, 2, 3]]],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B11", None, 1.11), Band("B04", "red", 0.665), Band("B08", "nir", 0.842)],
                },
                dim_types={"b": DimensionType.BANDS},
            ),
        ),
        # overlapping filters must not duplicate bands:
        (
            DataCube(
                [[[2, 3, 4]]],
                dims=("y", "x", "band"),
                coords={
                    "band": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842), Band("B11", None, 1.11)],
                },
                dim_types={"band": DimensionType.BANDS},
            ),
            ["B04", "B08", "red"],
            [[0.6, 0.7]],
            DataCube(
                [[[2, 3]]],
                dims=("y", "x", "band"),
                coords={
                    "band": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842)],
                },
                dim_types={"band": DimensionType.BANDS},
            ),
        ),
        # make sure we are handling cubes dimensions correctly by using cube 1x3x2x4:
        (
            DataCube(
                [
                    [[2, 3, 4, 6], [5, 6, 7, 6]],
                    [[1, 2, 3, 6], [4, 5, 6, 6]],
                    [[8, 9, 0, 6], [1, 2, 3, 6]],
                ],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842), Band("B11", None, 1.11), Band("B22")],
                },
                dim_types={"b": DimensionType.BANDS},
            ),
            ["B08"],
            None,
            DataCube(
                [
                    [[3], [6]],
                    [[2], [5]],
                    [[9], [2]],
                ],
                dims=("y", "x", "b"),
                coords={
                    "b": [Band("B08", "nir", 0.842)],
                },
                dim_types={"b": DimensionType.BANDS},
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
    assert_equal(result, expected_result)


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
    data = DataCube(
        [[[2, 3]]],
        dims=("y", "x", "b"),
        coords={"b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842)]},
        dim_types={"b": DimensionType.BANDS},
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
        (
            DataCube(
                [[[[2, 3]]]],
                dims=("y", "x", "b2", "b"),
                coords={
                    "b": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842)],
                    "b2": [Band("B22")],
                },
                dim_types={"b": DimensionType.BANDS, "b2": DimensionType.BANDS},
            ),
            "data",
            "Multiple dimensions of type 'bands' found.",
        ),
        (
            DataCube(
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
