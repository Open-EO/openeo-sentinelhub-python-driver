from datetime import datetime
import os
import sys

import numpy as np
import pytest
import xarray as xr
import pandas as pd
from sentinelhub import CRS, BBox

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessParameterInvalid, Band, assert_allclose
import logging


@pytest.fixture
def execute_process():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    def wrapped(arguments):
        return process.merge_cubes.merge_cubesEOTask(None, "", logger, {}, "node1", {}).process(arguments)

    return wrapped


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "cube1,cube2,overlap_resolver,expected_result",
    [
        # matching dims and coords:
        (
            xr.DataArray(
                [[0.1, 0.3]],
                dims=("a", "b"),
                coords={},
                attrs={},
            ),
            xr.DataArray(
                [[0.2, 0.8]],
                dims=("a", "b"),
                coords={},
                attrs={},
            ),
            {
                "process_graph": {
                    "resolver": {
                        "process_id": "subtract",
                        "arguments": {"x": {"from_parameter": "x"}, "y": {"from_parameter": "y"}},
                        "result": True,
                    }
                }
            },
            xr.DataArray(
                [[-0.1, -0.5]],
                dims=("a", "b"),
                coords={},
                attrs={},
            ),
        ),
        # the first cube is missing a dim:
        (
            xr.DataArray(
                [1.1, 1.3],
                dims=("b"),
                coords={},
                attrs={},
            ),
            xr.DataArray(
                [[0.2, 0.8], [0.7, 2], [1.4, np.nan]],
                dims=("a", "b"),
                coords={},
                attrs={},
            ),
            {
                "process_graph": {
                    "resolver": {
                        "process_id": "subtract",
                        "arguments": {"x": {"from_parameter": "x"}, "y": {"from_parameter": "y"}},
                        "result": True,
                    }
                }
            },
            xr.DataArray(
                [[0.9, 0.5], [0.4, -0.7], [-0.3, np.nan]],
                dims=("a", "b"),
                coords={},
                attrs={},
            ),
        ),
        # the second cube is missing a dim:
        (
            xr.DataArray(
                [[0.2, 0.8], [0.7, 2], [1.4, np.nan]],
                dims=("a", "b"),
                coords={},
                attrs={},
            ),
            xr.DataArray(
                [0.1, 0.3],
                dims=("b"),
                coords={},
                attrs={},
            ),
            {
                "process_graph": {
                    "resolver": {
                        "process_id": "subtract",
                        "arguments": {"x": {"from_parameter": "x"}, "y": {"from_parameter": "y"}},
                        "result": True,
                    }
                }
            },
            xr.DataArray(
                [[0.1, 0.5], [0.6, 1.7], [1.3, np.nan]],
                dims=("a", "b"),
                coords={},
                attrs={},
            ),
        ),
        # the first cube is missing a dim - with coords:
        (
            xr.DataArray(
                [1.1, 1.3],
                dims=("b"),
                coords={"b": ["asdf", "defg"]},
                attrs={},
            ),
            xr.DataArray(
                [[0.2, 0.8], [0.7, 2], [1.4, np.nan]],
                dims=("a", "b"),
                coords={"a": ["a", "b", "c"], "b": ["asdf", "defg"]},
                attrs={},
            ),
            {
                "process_graph": {
                    "resolver": {
                        "process_id": "subtract",
                        "arguments": {"x": {"from_parameter": "x"}, "y": {"from_parameter": "y"}},
                        "result": True,
                    }
                }
            },
            xr.DataArray(
                [[0.9, 0.5], [0.4, -0.7], [-0.3, np.nan]],
                dims=("a", "b"),
                coords={"a": ["a", "b", "c"], "b": ["asdf", "defg"]},
                attrs={},
            ),
        ),
        # the first cube is missing a dim - with Band coords:
        (
            xr.DataArray(
                [1.1, 1.3],
                dims=("b"),
                coords={"b": [Band("asdf"), Band("defg")]},
                attrs={},
            ),
            xr.DataArray(
                [[0.2, 0.8], [0.7, 2], [1.4, np.nan]],
                dims=("a", "b"),
                coords={"a": [Band("a"), Band("b"), Band("c")], "b": [Band("asdf"), Band("defg")]},
                attrs={},
            ),
            {
                "process_graph": {
                    "resolver": {
                        "process_id": "subtract",
                        "arguments": {"x": {"from_parameter": "x"}, "y": {"from_parameter": "y"}},
                        "result": True,
                    }
                }
            },
            xr.DataArray(
                [[0.9, 0.5], [0.4, -0.7], [-0.3, np.nan]],
                dims=("a", "b"),
                coords={"a": [Band("a"), Band("b"), Band("c")], "b": [Band("asdf"), Band("defg")]},
                attrs={},
            ),
        ),
        # normal concatenation:
        (
            xr.DataArray(
                [[0.1, np.nan], [0.2, 3], [np.nan, 4]],
                dims=("a", "b"),
                coords={"a": [Band("a"), Band("b"), Band("c")], "b": [Band("B01"), Band("B02")]},
                attrs={},
            ),
            xr.DataArray(
                [[0.2, 0.8], [0.7, 2], [1.4, np.nan]],
                dims=("a", "b"),
                coords={"a": [Band("a"), Band("b"), Band("c")], "b": [Band("B03"), Band("B04")]},
                attrs={},
            ),
            None,
            xr.DataArray(
                [[0.1, np.nan, 0.2, 0.8], [0.2, 3, 0.7, 2], [np.nan, 4, 1.4, np.nan]],
                dims=("a", "b"),
                coords={
                    "a": [Band("a"), Band("b"), Band("c")],
                    "b": [Band("B01"), Band("B02"), Band("B03"), Band("B04")],
                },
                attrs={},
            ),
        ),
        # merging, overlap on one coord:
        (
            xr.DataArray(
                [[0.1, np.nan], [0.2, 3], [np.nan, 4]],
                dims=("a", "b"),
                coords={"a": [Band("a"), Band("b"), Band("c")], "b": [Band("B01"), Band("B02")]},
                attrs={},
            ),
            xr.DataArray(
                [[0.2, 0.8], [0.7, 2], [1.4, np.nan]],
                dims=("a", "b"),
                coords={"a": [Band("a"), Band("b"), Band("c")], "b": [Band("B02"), Band("B03")]},
                attrs={},
            ),
            {
                "process_graph": {
                    "resolver": {
                        "process_id": "subtract",
                        "arguments": {"x": {"from_parameter": "x"}, "y": {"from_parameter": "y"}},
                        "result": True,
                    }
                }
            },
            xr.DataArray(
                [[0.1, np.nan, 0.8], [0.2, 2.3, 2], [np.nan, 2.6, np.nan]],
                dims=("a", "b"),
                coords={"a": [Band("a"), Band("b"), Band("c")], "b": [Band("B01"), Band("B02"), Band("B03")]},
                attrs={},
            ),
        ),
    ],
)
def test_correct(execute_process, cube1, cube2, overlap_resolver, expected_result):
    arguments = {"cube1": cube1, "cube2": cube2}
    if overlap_resolver is not None:
        arguments["overlap_resolver"] = overlap_resolver

    result = execute_process(arguments)
    assert_allclose(result, expected_result)


@pytest.mark.parametrize(
    "cube1,cube2,expected_exc_param,expected_message",
    [
        # missing dimensions:
        (
            xr.DataArray(
                [[0.2, 0.8]],
                dims=("a", "b"),
                coords={},
                attrs={},
            ),
            xr.DataArray(
                [[[[0.26, 0.81]]], [[[0.91, 0.31]]]],
                dims=("a", "b", "c", "d"),
                coords={},
                attrs={},
            ),
            "cube1/cube2",
            "Too many missing dimensions (c, d), can be at most one.",
        ),
        # missing dimensions in both of the cubes:
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
                dims=("a", "b", "c", "d"),
                coords={},
                attrs={},
            ),
            xr.DataArray(
                [[[[0.26, 0.81]]], [[[0.91, 0.31]]]],
                dims=("a", "b", "e", "f"),
                coords={},
                attrs={},
            ),
            "cube1/cube2",
            "Too many missing dimensions (c, d, e, f), can be at most one.",
        ),
        # mismatched coords in more than one dim:
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
                dims=("a", "b", "c", "d"),
                coords={"a": [1, 2, 3], "b": [1]},
                attrs={},
            ),
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
                dims=("a", "b", "c", "d"),
                coords={"a": [1, 2, 4], "b": [2]},
                attrs={},
            ),
            "cube1/cube2",
            "Too many mismatched dimensions (a, b), can be at most one.",
        ),
        # mismatched coords in more than one dim - different coords lengths:
        (
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]]],
                dims=("a", "b", "c", "d"),
                coords={"a": [1, 2], "b": [1]},
                attrs={},
            ),
            xr.DataArray(
                [[[[0.2, 0.8]]], [[[0.9, 0.3]]], [[[0.5, 0.5]]]],
                dims=("a", "b", "c", "d"),
                coords={"a": [1, 2, 4], "b": [2]},
                attrs={},
            ),
            "cube1/cube2",
            "Too many mismatched dimensions (a, b), can be at most one.",
        ),
        # matching dims and coords, but no overlap_resolver:
        (
            xr.DataArray(
                [[0.1, 0.3]],
                dims=("a", "b"),
                coords={},
                attrs={},
            ),
            xr.DataArray(
                [[0.2, 0.8]],
                dims=("a", "b"),
                coords={},
                attrs={},
            ),
            "overlap_resolver",
            "Overlapping data cubes, but no overlap resolver has been specified (OverlapResolverMissing).",
        ),
        # one cube is missing a dim, but no resolver:
        (
            xr.DataArray(
                [0.1, 0.3],
                dims=("b"),
                coords={},
                attrs={},
            ),
            xr.DataArray(
                [[0.2, 0.8], [0.7, 2], [1.4, 3]],
                dims=("a", "b"),
                coords={},
                attrs={},
            ),
            "overlap_resolver",
            "Overlapping data cubes, but no overlap resolver has been specified (OverlapResolverMissing).",
        ),
        # normal merging on one coord, missing resolver:
        (
            xr.DataArray(
                [[0.1, np.nan], [0.2, 3], [np.nan, 4]],
                dims=("a", "b"),
                coords={"a": [Band("a"), Band("b"), Band("c")], "b": [Band("B01"), Band("B02")]},
                attrs={},
            ),
            xr.DataArray(
                [[0.2, 0.8], [0.7, 2], [1.4, np.nan]],
                dims=("a", "b"),
                coords={"a": [Band("a"), Band("b"), Band("c")], "b": [Band("B02"), Band("B04")]},
                attrs={},
            ),
            "overlap_resolver",
            "Overlapping data cubes, but no overlap resolver has been specified (OverlapResolverMissing).",
        ),
    ],
)
def test_exception(execute_process, cube1, cube2, expected_exc_param, expected_message):
    arguments = {"cube1": cube1, "cube2": cube2}
    with pytest.raises(ProcessParameterInvalid) as ex:
        result = execute_process(arguments)
    assert ex.value.args == ("merge_cubes", expected_exc_param, expected_message)

    # repeat the test with switched cube1/cube2:
    arguments = {"cube1": cube2, "cube2": cube1}
    with pytest.raises(ProcessParameterInvalid) as ex:
        result = execute_process(arguments)
    assert ex.value.args == ("merge_cubes", expected_exc_param, expected_message)
