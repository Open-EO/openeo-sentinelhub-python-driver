from datetime import datetime
import os
import sys

import numpy as np
import pytest
import xarray as xr

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessParameterInvalid


@pytest.fixture
def execute_process():
    def wrapped(arguments):
        return process.rename_labels.rename_labelsEOTask(None, "", None, {}, "node1", {}).process(arguments)

    return wrapped


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "data,dimension,target,source,expected_result",
    [
        (
            xr.DataArray([0, 1, 2], dims=("x",), coords={"x": [10, 20, 30]}),
            "x",
            [100, 200, 300],
            [10, 20, 30],
            xr.DataArray([0, 1, 2], dims=("x",), coords={"x": [100, 200, 300]}),
        ),
        (
            xr.DataArray([0, 1, 2], dims=("x",), coords={"x": ["10", "20", "30"]}),
            "x",
            ["100", "200", "300"],
            ["10", "20", "30"],
            xr.DataArray([0, 1, 2], dims=("x",), coords={"x": ["100", "200", "300"]}),
        ),
        (
            xr.DataArray([0, 1, 2], dims=("x",), coords={"x": [10, 20, 30]}),
            "x",
            [100, 300, 200],
            [10, 30, 20],
            xr.DataArray([0, 1, 2], dims=("x",), coords={"x": [100, 200, 300]}),
        ),
        (
            xr.DataArray([0, 1, 2], dims=("x",), coords={"x": [10, 20, 30]}),
            "x",
            [100, 300],
            [10, 30],
            xr.DataArray([0, 1, 2], dims=("x",), coords={"x": [100, 20, 300]}),
        ),
        (
            xr.DataArray([0, 1, 2], dims=("x",), coords={"x": [0, 1, 2]}),
            "x",
            [100, 200, 300],
            [],
            xr.DataArray([0, 1, 2], dims=("x",), coords={"x": [100, 200, 300]}),
        ),
        (
            xr.DataArray([0, 1, 2], dims=("x",), coords={"x": [0, 1, 2]}),
            "x",
            [100, 200],
            [],
            xr.DataArray([0, 1, 2], dims=("x",), coords={"x": [100, 200, 2]}),
        ),
    ],
)
def test_rename_labels(execute_process, data, dimension, target, source, expected_result):
    arguments = {
        "data": data,
        "dimension": dimension,
        "target": target,
        "source": source,
    }
    original_data = data.copy(deep=True)
    result = execute_process(arguments)
    xr.testing.assert_allclose(result, expected_result)

    # make sure we didn't change the original input:
    xr.testing.assert_allclose(data, original_data)


@pytest.mark.parametrize(
    "data,dimension,target,source,expected_exc_param,expected_exc_msg",
    [
        (
            xr.DataArray([0, 1, 2], dims=("x",), coords={"x": [2, 3, 4]}),
            "x",
            [100, 200, 300],
            [],
            "source",
            "With source not supplied, data labels must be enumerated (LabelsNotEnumerated).",
        ),
        (
            xr.DataArray([0, 1, 2], dims=("x",), coords={"x": [2, 3, 4]}),
            "x",
            [100, 200, 300],
            [10, 20],
            "source/target",
            "Size of source and target does not match (LabelMismatch).",
        ),
        (
            xr.DataArray([0, 1, 2], dims=("x",), coords={"x": [10, 20, 30]}),
            "x",
            [3, 4, 2],
            [10, 20, 40],
            "source",
            "Source label / enumeration index does not exist (LabelNotAvailable).",
        ),
    ],
)
def test_rename_labels_exceptions(
    execute_process, data, dimension, target, source, expected_exc_param, expected_exc_msg
):
    arguments = {
        "data": data,
        "dimension": dimension,
        "target": target,
        "source": source,
    }
    original_data = data.copy(deep=True)
    with pytest.raises(ProcessParameterInvalid) as ex:
        result = execute_process(arguments)
    assert ex.value.args == ("rename_labels", expected_exc_param, expected_exc_msg)
