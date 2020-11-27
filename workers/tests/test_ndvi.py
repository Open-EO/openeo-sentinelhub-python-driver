import pytest
import sys, os
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
def ndviEOTask():
    return process.ndvi.ndviEOTask(None, "", None, {}, "node1", {})


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "data,nir,red,target_band,expected_result",
    [
        (
            DataCube(
                [[[2, 3]]],
                dims=("y", "x", "band"),
                coords={
                    "band": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842)],
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "band": DimensionType.BANDS,
                },
            ),
            None,
            None,
            None,
            DataCube(
                [[0.2]],
                dims=("y", "x"),
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                },
            ),
        ),
        (
            DataCube(
                [[[2, 3]]],
                dims=("y", "x", "band"),
                coords={
                    "band": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842)],
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "band": DimensionType.BANDS,
                },
            ),
            None,
            None,
            "my_ndvi",
            DataCube(
                [[[2, 3, 0.2]]],
                dims=("y", "x", "band"),
                coords={
                    "band": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842), Band("my_ndvi")],
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "band": DimensionType.BANDS,
                },
            ),
        ),
        (
            DataCube(
                [[[2, 3]]],
                dims=("y", "x", "band"),
                coords={
                    "band": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842)],
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "band": DimensionType.BANDS,
                },
            ),
            "nir",
            "red",
            None,
            DataCube(
                [[0.2]],
                dims=("y", "x"),
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                },
            ),
        ),
        (
            DataCube(
                [[[2, 3]]],
                dims=("y", "x", "band"),
                coords={
                    "band": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842)],
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "band": DimensionType.BANDS,
                },
            ),
            "red",  # switch
            "nir",
            None,
            DataCube(
                [[-0.2]],
                dims=("y", "x"),
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                },
            ),
        ),
        (
            DataCube(
                [[[2, 3]]],
                dims=("y", "x", "band"),
                coords={
                    "band": [Band("B01", "red", 0.665), Band("B02", "nir", 0.842)],
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "band": DimensionType.BANDS,
                },
            ),
            "B01",  # band names instead of aliases (switched)
            "B02",
            None,
            DataCube(
                [[-0.2]],
                dims=("y", "x"),
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                },
            ),
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
    assert_equal(result, expected_result)


@pytest.mark.parametrize(
    "data,nir,red,target_band,expected_exc_param,expected_exc_msg",
    [
        (
            DataCube([[2, 3]], dims=("y", "x")),
            None,
            None,
            None,
            "data",
            "Dimension 'band' is missing (DimensionAmbiguous).",
        ),
        # Temporarily disabled because we can't really check the dimension type at the moment:
        # (
        #     DataCube([[[2, 3]]], dims=("y", "x", "band")),
        #     None,
        #     None,
        #     None,
        #     "data",
        #     "Dimension 'band' does not contain bands (DimensionAmbiguous).",
        # ),
        (
            DataCube(
                [[[2, 3]]],
                dims=("y", "x", "band"),
                coords={
                    "band": [Band("B04", None, 0.665), Band("B08", None, 0.842)],
                },
            ),
            None,
            None,
            None,
            "nir",
            "Parameter does not match any band (NirBandAmbiguous).",
        ),
        (
            DataCube(
                [[[2, 3]]],
                dims=("y", "x", "band"),
                coords={
                    "band": [Band("B04", "nir", 0.665), Band("B08", None, 0.842)],
                },
            ),
            None,
            None,
            None,
            "red",
            "Parameter does not match any band (RedBandAmbiguous).",
        ),
        (
            DataCube(
                [[[2, 3, 11]]],
                dims=("y", "x", "band"),
                coords={
                    "band": [Band("B04", "nir", 0.665), Band("B08", "red", 0.842), Band("B11", None, 0.999)],
                },
            ),
            None,
            None,
            "B11",
            "target_band",
            "Band name already exists (BandExists).",
        ),
        (
            DataCube(
                [[[2, 3, 11]]],
                dims=("y", "x", "band"),
                coords={
                    "band": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842), Band("B11", "B11alias", 0.999)],
                },
            ),
            None,
            None,
            "B11alias",
            "target_band",
            "Band name already exists (BandExists).",
        ),
        (
            DataCube(
                [[[2, 3]]],
                dims=("y", "x", "band"),
                coords={
                    "band": [Band("B04", "red", 0.665), Band("B08", "nir", 0.842)],
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
