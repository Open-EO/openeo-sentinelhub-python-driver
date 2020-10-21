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
        return process.add_dimension.add_dimensionEOTask(None, "", None, {}, "node1", {}).process(arguments)

    return wrapped


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "data,name,label,expected_result",
    [
        (
            xr.DataArray(
                [1, 2, 3, 4],
                dims=["t"],
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                        datetime(2014, 3, 7),
                    ]
                },
            ),
            "x",
            42,
            xr.DataArray(
                [[1, 2, 3, 4]],
                dims=["x", "t"],
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                        datetime(2014, 3, 7),
                    ],
                    "x": [42],
                },
            ),
        ),
    ],
)
def test_correct(execute_process, data, name, label, expected_result):

    arguments = {
        "data": data,
        "name": name,
        "label": label,
    }
    result = execute_process(arguments)
    xr.testing.assert_allclose(result, expected_result)


def test_dimension_exists(execute_process):

    arguments = {
        "data": xr.DataArray(
            [1],
            dims=["t"],
            coords={
                "t": [
                    datetime(2014, 3, 4),
                ]
            },
        ),
        "name": "t",
        "label": "some_label",
    }
    with pytest.raises(ProcessParameterInvalid) as ex:
        result = execute_process(arguments)
    assert ex.value.args == (
        "add_dimension",
        "name",
        "A dimension with the specified name already exists.",
    )
