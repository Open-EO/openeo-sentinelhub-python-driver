from datetime import datetime
import os
import sys

import numpy as np
import pytest
import xarray as xr

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessParameterInvalid
import logging


@pytest.fixture
def execute_process():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    def wrapped(arguments, logger=logger):
        return process.merge_cubes.merge_cubesEOTask(None, "", logger, {}, "node1", {}).process(arguments)

    return wrapped


###################################
# tests:
###################################


def test_identical_cubes(execute_process):
    cube1 = xr.DataArray(
        [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
        dims=("t", "y", "x", "band"),
        coords={
            "t": [
                datetime(2014, 3, 4),
                datetime(2014, 3, 5),
                datetime(2014, 3, 6),
            ],
            "band": ["B01", "B02"],
            "x": [0],
            "y": [0],
        },
    )
    cube2 = cube1.copy()
    arguments = {"cube1": cube1, "cube2": cube2}
    result = execute_process(arguments)
    xr.testing.assert_allclose(result, cube1)


def test_temporally_separated_cubes(execute_process):
    cube1 = xr.DataArray(
        [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
        dims=("t", "y", "x", "band"),
        coords={
            "t": [
                datetime(2014, 3, 4),
                datetime(2014, 3, 5),
                datetime(2014, 3, 6),
            ],
            "band": ["B01", "B02"],
        },
    )
    cube2 = xr.DataArray(
        [[[[0.26, 0.81]]], [[[0.91, 0.31]]]],
        dims=("t", "y", "x", "band"),
        coords={
            "t": [
                datetime(2014, 3, 8),
                datetime(2014, 3, 9),
            ],
            "band": ["B01", "B02"],
        },
    )
    expected_cube = cube1 = xr.DataArray(
        [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]], [[[0.26, 0.81]]], [[[0.91, 0.31]]]],
        dims=("t", "y", "x", "band"),
        coords={
            "t": [
                datetime(2014, 3, 4),
                datetime(2014, 3, 5),
                datetime(2014, 3, 6),
                datetime(2014, 3, 8),
                datetime(2014, 3, 9),
            ],
            "band": ["B01", "B02"],
            "x": [0],
            "y": [0],
        },
    )
    arguments = {"cube1": cube1, "cube2": cube2}
    result = execute_process(arguments)
    xr.testing.assert_allclose(result, expected_cube)


def test_with_overlap_conflicts(execute_process):
    cube1 = xr.DataArray(
        [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
        dims=("t", "y", "x", "band"),
        coords={
            "t": [
                datetime(2014, 3, 4),
                datetime(2014, 3, 5),
                datetime(2014, 3, 6),
            ],
            "band": ["B01", "B02"],
        },
    )
    cube2 = xr.DataArray(
        [[[[0.26, 0.81]]], [[[0.91, 0.31]]]],
        dims=("t", "y", "x", "band"),
        coords={
            "t": [
                datetime(2014, 3, 5),
                datetime(2014, 3, 6),
            ],
            "band": ["B01", "B02"],
        },
    )
    expected_cube = xr.DataArray(
        [[[[0.2, 0.8]]], [[[1.16, 1.11]]], [[[1.41, 0.81]]]],
        dims=("t", "y", "x", "band"),
        coords={
            "t": [
                datetime(2014, 3, 4),
                datetime(2014, 3, 5),
                datetime(2014, 3, 6),
            ],
            "band": ["B01", "B02"],
            "x": [0],
            "y": [0],
        },
    )
    overlap_resolver = {
        "process_graph": {
            "resolver": {
                "process_id": "sum",
                "arguments": {"data": [{"from_argument": "x"}, {"from_argument": "y"}]},
                "result": True,
            }
        }
    }
    arguments = {"cube1": cube1, "cube2": cube2, "overlap_resolver": overlap_resolver}
    result = execute_process(arguments)
    xr.testing.assert_allclose(result, expected_cube)


def test_with_overlap_conflicts_and_no_overlap_resolver(execute_process):
    cube1 = xr.DataArray(
        [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
        dims=("t", "y", "x", "band"),
        coords={
            "t": [
                datetime(2014, 3, 4),
                datetime(2014, 3, 5),
                datetime(2014, 3, 6),
            ],
            "band": ["B01", "B02"],
        },
    )
    cube2 = xr.DataArray(
        [[[[0.26, 0.81]]], [[[0.91, 0.31]]]],
        dims=("t", "y", "x", "band"),
        coords={
            "t": [
                datetime(2014, 3, 5),
                datetime(2014, 3, 6),
            ],
            "band": ["B01", "B02"],
        },
    )
    arguments = {"cube1": cube1, "cube2": cube2}
    with pytest.raises(ProcessParameterInvalid) as ex:
        result = execute_process(arguments)
    assert ex.value.args == (
        "merge_cubes",
        "overlap_resolver",
        "Overlapping data cubes, but no overlap resolver has been specified.",
    )


def test_with_different_dimensions(execute_process):
    cube1 = xr.DataArray(
        [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
        dims=("t", "y", "x", "band"),
        coords={
            "t": [
                datetime(2014, 3, 4),
                datetime(2014, 3, 5),
                datetime(2014, 3, 6),
            ],
            "band": ["B01", "B02"],
        },
    )
    cube2 = xr.DataArray(
        [[[0.26, 0.81]]],
        dims=("y", "x", "band"),
        coords={
            "band": ["B01", "B02"],
        },
    )
    expected_cube = xr.DataArray(
        [[[[0.46, 1.61]]], [[[1.16, 1.11]]], [[[0.76, 1.31]]]],
        dims=("t", "y", "x", "band"),
        coords={
            "t": [
                datetime(2014, 3, 4),
                datetime(2014, 3, 5),
                datetime(2014, 3, 6),
            ],
            "band": ["B01", "B02"],
            "x": [0],
            "y": [0],
        },
    )
    overlap_resolver = {
        "process_graph": {
            "resolver": {
                "process_id": "sum",
                "arguments": {"data": [{"from_argument": "x"}, {"from_argument": "y"}]},
                "result": True,
            }
        }
    }
    arguments = {"cube1": cube1, "cube2": cube2, "overlap_resolver": overlap_resolver}
    result = execute_process(arguments)
    xr.testing.assert_allclose(result, expected_cube)
