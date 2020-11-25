import pytest
import sys, os
from datetime import datetime

import xarray as xr
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessParameterInvalid, Band, DataCube, DimensionType, assert_equal


@pytest.fixture
def execute_array_element_process():
    def wrapped(data, index=None, label=None, return_nodata=False):
        arguments = {"data": data}
        if return_nodata is not None:
            arguments["return_nodata"] = return_nodata
        if index is not None:
            arguments["index"] = index
        if label is not None:
            arguments["label"] = label
        return process.array_element.array_elementEOTask(None, "", None, {}, "arrayel1", {}).process(arguments)

    return wrapped


def bands():
    return [Band("B04", "red", 0.665), Band("B08", "nir", 0.842)]


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "data,return_nodata,index,expected_result",
    [([9, 8, 7, 6, 5], None, 2, 7), (["A", "B", "C"], None, 0, "A"), ([], True, 0, None)],
)
def test_examples(execute_array_element_process, data, return_nodata, index, expected_result):
    """
    Test array_element process with examples from https://processes.openeo.org/1.0.0/#array_element
    """
    result = execute_array_element_process(data, index=index, return_nodata=return_nodata)
    assert result == expected_result


@pytest.mark.parametrize(
    "data,index,expected_result",
    [
        (
            DataCube(
                [[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                    ],
                    "band": bands(),
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "t": DimensionType.TEMPORAL,
                    "band": DimensionType.BANDS,
                },
                attrs={"reduce_by": ["band"]},
            ),
            0,
            DataCube(
                [[[0.1, 0.15], [0.05, -0.9]]],
                dims=("t", "y", "x"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                    ],
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "t": DimensionType.TEMPORAL,
                },
                attrs={"reduce_by": ["band"]},
            ),
        ),
        (
            DataCube(
                [[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                    ],
                    "band": bands(),
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "t": DimensionType.TEMPORAL,
                    "band": DimensionType.BANDS,
                },
                attrs={"reduce_by": ["y"]},
            ),
            1,
            DataCube(
                [[[0.05, 0.1], [-0.9, 0.05]]],
                dims=("t", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                    ],
                    "band": bands(),
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "t": DimensionType.TEMPORAL,
                    "band": DimensionType.BANDS,
                },
                attrs={"reduce_by": ["y"]},
            ),
        ),
    ],
)
def test_index(execute_array_element_process, data, index, expected_result):
    """
    Test array_element process with index parameter
    """
    result = execute_array_element_process(data, index=index)
    assert_equal(result, expected_result)


@pytest.mark.parametrize(
    "data,label,expected_result",
    [
        (
            DataCube(
                [[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                    ],
                    "band": bands(),
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "t": DimensionType.TEMPORAL,
                    "band": DimensionType.BANDS,
                },
                attrs={"reduce_by": ["band"]},
            ),
            "B04",
            DataCube(
                [[[0.1, 0.15], [0.05, -0.9]]],
                dims=("t", "y", "x"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                    ],
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "t": DimensionType.TEMPORAL,
                },
                attrs={"reduce_by": ["band"]},
            ),
        ),
        (
            DataCube(
                [[[[0.1, 0.15], [0.15, 0.2]]], [[[0.05, 0.1], [-0.9, 0.05]]], [[[-0.05, 3.1], [0.99, 0.02]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": bands(),
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "t": DimensionType.TEMPORAL,
                    "band": DimensionType.BANDS,
                },
                attrs={"reduce_by": ["t"]},
            ),
            "2014-03-05",
            DataCube(
                [[[0.05, 0.1], [-0.9, 0.05]]],
                dims=("y", "x", "band"),
                coords={
                    "band": bands(),
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "band": DimensionType.BANDS,
                },
                attrs={"reduce_by": ["y"]},
            ),
        ),
        (
            DataCube(
                [[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                    ],
                    "band": bands(),
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "t": DimensionType.TEMPORAL,
                    "band": DimensionType.BANDS,
                },
                attrs={"reduce_by": ["band"]},
            ),
            "red",
            DataCube(
                [[[0.1, 0.15], [0.05, -0.9]]],
                dims=("t", "y", "x"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                    ],
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "t": DimensionType.TEMPORAL,
                },
                attrs={"reduce_by": ["band"]},
            ),
        ),
    ],
)
def test_label(execute_array_element_process, data, label, expected_result):
    """
    Test array_element process with label parameter
    """
    result = execute_array_element_process(data, label=label)
    assert_equal(result, expected_result)


@pytest.mark.parametrize(
    "data,index,label,expected_error",
    [
        (
            DataCube(
                [2],
                dims=("t"),
            ),
            None,
            None,
            (
                "array_element",
                "index/label",
                "The process 'array_element' requires either the 'index' or 'label' parameter to be set. (ArrayElementParameterMissing)",
            ),
        ),
        (
            DataCube(
                [2],
                dims=("t"),
            ),
            0,
            "B01",
            (
                "array_element",
                "index/label",
                "The process 'array_element' only allows that either the 'index' or the 'label' parameter is set. (ArrayElementParameterConflict)",
            ),
        ),
        (
            DataCube(
                [[[[0.1, 0.15], [0.15, 0.2]]], [[[0.05, 0.1], [-0.9, 0.05]]], [[[-0.05, 3.1], [0.99, 0.02]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": bands(),
                },
                attrs={"reduce_by": ["t"]},
            ),
            None,
            "2014-03-07",
            (
                "array_element",
                "index/label",
                "The array has no element with the specified index or label. (ArrayElementNotAvailable)",
            ),
        ),
        (
            DataCube(
                [[[[0.1, 0.15], [0.15, 0.2]]], [[[0.05, 0.1], [-0.9, 0.05]]], [[[-0.05, 3.1], [0.99, 0.02]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": bands(),
                },
                attrs={"reduce_by": ["t"]},
            ),
            15,
            None,
            (
                "array_element",
                "index/label",
                "The array has no element with the specified index or label. (ArrayElementNotAvailable)",
            ),
        ),
        (
            DataCube(
                [[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                    ],
                    "band": bands(),
                },
                attrs={"reduce_by": ["band"]},
            ),
            None,
            "0.665",
            (
                "array_element",
                "index/label",
                "The array has no element with the specified index or label. (ArrayElementNotAvailable)",
            ),
        ),
    ],
)
def test_errors(execute_array_element_process, data, label, index, expected_error):
    """
    Test array_element errors
    """
    with pytest.raises(ProcessParameterInvalid) as ex:
        result = execute_array_element_process(data, index=index, label=label)
    assert ex.value.args == expected_error


@pytest.mark.parametrize(
    "data,index,label,expected_result",
    [
        (
            DataCube(
                [[[[0.1, 0.15], [0.15, 0.2]]], [[[0.05, 0.1], [-0.9, 0.05]]], [[[-0.05, 3.1], [0.99, 0.02]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": bands(),
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "t": DimensionType.TEMPORAL,
                    "band": DimensionType.BANDS,
                },
                attrs={"reduce_by": ["t"]},
            ),
            4,
            None,
            DataCube(
                [[[np.nan, np.nan], [np.nan, np.nan]]],
                dims=("y", "x", "band"),
                coords={
                    "band": bands(),
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "band": DimensionType.BANDS,
                },
                attrs={"reduce_by": ["t"]},
            ),
        ),
        (
            DataCube(
                [[[[0.1, 0.15], [0.15, 0.2]]], [[[0.05, 0.1], [-0.9, 0.05]]], [[[-0.05, 3.1], [0.99, 0.02]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": bands(),
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "t": DimensionType.TEMPORAL,
                    "band": DimensionType.BANDS,
                },
                attrs={"reduce_by": ["t"]},
            ),
            None,
            "2014-03-07",
            DataCube(
                [[[np.nan, np.nan], [np.nan, np.nan]]],
                dims=("y", "x", "band"),
                coords={
                    "band": bands(),
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "band": DimensionType.BANDS,
                },
                attrs={"reduce_by": ["t"]},
            ),
        ),
        (
            DataCube(
                [[[[0.1, 0.15], [0.15, 0.2]]], [[[0.05, 0.1], [-0.9, 0.05]]], [[[-0.05, 3.1], [0.99, 0.02]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": bands(),
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "t": DimensionType.TEMPORAL,
                    "band": DimensionType.BANDS,
                },
                attrs={"reduce_by": ["band"]},
            ),
            None,
            "B01",
            DataCube(
                [[[np.nan, np.nan]], [[np.nan, np.nan]], [[np.nan, np.nan]]],
                dims=("t", "y", "x"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                },
                dim_types={
                    "x": DimensionType.SPATIAL,
                    "y": DimensionType.SPATIAL,
                    "t": DimensionType.TEMPORAL,
                },
                attrs={"reduce_by": ["band"]},
            ),
        ),
    ],
)
def test_return_nodata(execute_array_element_process, data, label, index, expected_result):
    """
    Test array_element with return_nodata parameter
    """
    result = execute_array_element_process(data, index=index, label=label, return_nodata=True)
    assert_equal(result, expected_result)
