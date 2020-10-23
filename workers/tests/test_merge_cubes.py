from datetime import datetime
import os
import sys

import numpy as np
import pytest
import xarray as xr
import pandas as pd

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


def bands():
    return pd.MultiIndex.from_arrays(
        [["B04", "B08"], ["red", "nir"], [0.665, 0.842]], names=("_name", "_alias", "_wavelength")
    )


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "cube1,cube2,expected_cube",
    [
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": bands(),
                },
            ),
            xr.DataArray(
                [[[[0.26, 0.81]]], [[[0.91, 0.31]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 8),
                        datetime(2014, 3, 9),
                    ],
                    "band": bands(),
                },
            ),
            xr.DataArray(
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
                    "band": bands(),
                    "x": [0],
                    "y": [0],
                },
            ),
        ),
    ],
)
def test_separated_cubes(execute_process, cube1, cube2, expected_cube):
    arguments = {"cube1": cube1, "cube2": cube2}
    result = execute_process(arguments)
    xr.testing.assert_allclose(result, expected_cube)


@pytest.mark.parametrize(
    "cube1,cube2,overlap_resolver,expected_cube",
    [
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": bands(),
                },
            ),
            xr.DataArray(
                [[[[0.26, 0.81]]], [[[0.91, 0.31]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": bands(),
                },
            ),
            {
                "process_graph": {
                    "resolver": {
                        "process_id": "sum",
                        "arguments": {"data": [{"from_argument": "x"}, {"from_argument": "y"}]},
                        "result": True,
                    }
                }
            },
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[1.16, 1.11]]], [[[1.41, 0.81]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": bands(),
                    "x": [0],
                    "y": [0],
                },
            ),
        ),
    ],
)
def test_with_overlap_conflicts(execute_process, cube1, cube2, overlap_resolver, expected_cube):
    arguments = {"cube1": cube1, "cube2": cube2, "overlap_resolver": overlap_resolver}
    result = execute_process(arguments)
    xr.testing.assert_allclose(result, expected_cube)


@pytest.mark.parametrize(
    "cube1,cube2",
    [
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": bands(),
                },
            ),
            xr.DataArray(
                [[[[0.26, 0.81]]], [[[0.91, 0.31]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": bands(),
                },
            ),
        ),
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": bands(),
                    "x": [0],
                    "y": [0],
                },
            ),
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": bands(),
                    "x": [0],
                    "y": [0],
                },
            ),
        ),
        (
            xr.DataArray(
                [[None]],
                dims=("y", "x"),
                coords={
                    "x": [0],
                    "y": [0],
                },
            ),
            xr.DataArray(
                [[None]],
                dims=("y", "x"),
                coords={
                    "x": [0],
                    "y": [0],
                },
            ),
        ),
    ],
)
def test_with_overlap_conflicts_and_no_overlap_resolver(execute_process, cube1, cube2):
    arguments = {"cube1": cube1, "cube2": cube2}
    with pytest.raises(ProcessParameterInvalid) as ex:
        result = execute_process(arguments)
    assert ex.value.args == (
        "merge_cubes",
        "overlap_resolver",
        "Overlapping data cubes, but no overlap resolver has been specified. (OverlapResolverMissing)",
    )


@pytest.mark.parametrize(
    "cube1,cube2,overlap_resolver,expected_cube",
    [
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": bands(),
                },
            ),
            xr.DataArray(
                [[[0.26, 0.81]]],
                dims=("y", "x", "band"),
                coords={
                    "band": bands(),
                },
            ),
            {
                "process_graph": {
                    "resolver": {
                        "process_id": "sum",
                        "arguments": {"data": [{"from_argument": "x"}, {"from_argument": "y"}]},
                        "result": True,
                    }
                }
            },
            xr.DataArray(
                [[[[0.46, 1.61]]], [[[1.16, 1.11]]], [[[0.76, 1.31]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": bands(),
                    "x": [0],
                    "y": [0],
                },
            ),
        ),
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": bands(),
                },
            ),
            xr.DataArray(
                [0.26, 0.81],
                dims=("band"),
                coords={
                    "band": bands(),
                },
            ),
            {
                "process_graph": {
                    "resolver": {
                        "process_id": "sum",
                        "arguments": {"data": [{"from_argument": "x"}, {"from_argument": "y"}]},
                        "result": True,
                    }
                }
            },
            xr.DataArray(
                [[[[0.46, 1.61]]], [[[1.16, 1.11]]], [[[0.76, 1.31]]]],
                dims=("t", "y", "x", "band"),
                coords={
                    "t": [
                        datetime(2014, 3, 4),
                        datetime(2014, 3, 5),
                        datetime(2014, 3, 6),
                    ],
                    "band": bands(),
                    "x": [0],
                    "y": [0],
                },
            ),
        ),
    ],
)
def test_with_different_dimensions(execute_process, cube1, cube2, overlap_resolver, expected_cube):
    # Documentation doesn't make it clear whether cubes with different dimensions and mismatching labels on a common
    # dimension are "compatible" or not.
    # If cubes have different dimensions, we merge them into a higher dimensional cube which includes all, and then
    # merge and resolve overlap in (at most one) common overlapping dimension.
    arguments = {"cube1": cube1, "cube2": cube2, "overlap_resolver": overlap_resolver}
    result = execute_process(arguments)
    xr.testing.assert_allclose(result, expected_cube)


@pytest.mark.parametrize(
    "cube1,cube2",
    [
        (
            xr.DataArray(
                [[0.2]],
                dims=("y", "x"),
                coords={
                    "x": [0],
                    "y": [0],
                },
            ),
            xr.DataArray(
                [[0.2]],
                dims=("y", "x"),
                coords={
                    "x": [1],
                    "y": [1],
                },
            ),
        ),
    ],
)
def test_incompatible_cubes(execute_process, cube1, cube2):
    arguments = {"cube1": cube1, "cube2": cube2}
    with pytest.raises(ProcessParameterInvalid) as ex:
        result = execute_process(arguments)
    assert ex.value.args == ("merge_cubes", "cube1/cube2", "Only one of the dimensions can have different labels.")
