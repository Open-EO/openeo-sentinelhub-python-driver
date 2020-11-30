import pytest
import sys, os
import datetime
import logging
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessParameterInvalid, DataCube, assert_equal


@pytest.fixture
def generate_data():
    def _construct(data=[[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]], dims=("t", "y", "x", "band")):
        xrdata = DataCube(data, dims=dims)
        return xrdata

    return _construct


@pytest.fixture
def execute_apply_process(generate_data):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    def wrapped(data_arguments={}, process_callback=None, logger=logger):
        arguments = {}
        if data_arguments is not None:
            arguments["data"] = generate_data(**data_arguments)
        if process_callback is not None:
            arguments["process"] = process_callback

        return process.apply.applyEOTask(None, "", logger, {}, "apply1", {}).process(arguments)

    return wrapped


@pytest.fixture
def execute_process():
    logger = logging.getLogger()

    def wrapped(arguments):
        return process.apply.applyEOTask(None, "", logger, {}, "apply1", {}).process(arguments)

    return wrapped


###################################
# tests:
###################################


def test_apply_simple(execute_process):
    """
    Test apply process with linear_scale_range
    """
    # prepare data:
    data = DataCube(
        [[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]],
        dims=("t", "y", "x", "band"),
    )
    process_callback = {
        "lsr": {
            "process_id": "linear_scale_range",
            "arguments": {
                "x": {"from_parameter": "x"},
                "inputMin": 0,
                "inputMax": 1,
                "outputMin": 1,
                "outputMax": 2,
            },
            "result": True,
        }
    }

    # execute process:
    result = execute_process(
        {
            "data": data,
            "process": {
                "process_graph": process_callback,
            },
        }
    )

    # check results:
    expected_result = DataCube(
        [[[[1.1, 1.15], [1.15, 1.2]], [[1.05, 1.1], [0.1, 1.05]]]],
        dims=("t", "y", "x", "band"),
    )
    assert_equal(result, expected_result)
    assert result.attrs.get("simulated_datatype", None) is None


@pytest.mark.skip(
    "apply can no longer be called recursively because of data types (callback gets a number, apply expects datacube)"
)
def test_recursive_callback(execute_apply_process, generate_data):
    """
    Test apply process with a recursive callback, which applies linear_scale_range multiple times
    """
    process_callback = {
        "process_graph": {
            "p1": {
                "process_id": "apply",
                "arguments": {
                    "data": {"from_parameter": "data"},
                    "process": {
                        "process_graph": {
                            "p1": {
                                "process_id": "apply",
                                "arguments": {
                                    "data": {"from_parameter": "data"},
                                    "process": {
                                        "process_graph": {
                                            "lsr": {
                                                "process_id": "linear_scale_range",
                                                "arguments": {
                                                    "x": {"from_parameter": "x"},
                                                    "inputMin": -1,
                                                    "inputMax": 1,
                                                    "outputMax": 1000,
                                                },
                                                "result": True,
                                            }
                                        }
                                    },
                                },
                            },
                            "lsr": {
                                "process_id": "linear_scale_range",
                                "arguments": {
                                    "x": {"from_node": "p1"},
                                    "inputMin": 0,
                                    "inputMax": 1000,
                                    "outputMin": -1000,
                                },
                                "result": True,
                            },
                        }
                    },
                },
            },
            "lsr": {
                "process_id": "linear_scale_range",
                "arguments": {
                    "x": {"from_node": "p1"},
                    "inputMin": -1000,
                    "inputMax": 1,
                    "outputMin": 0,
                    "outputMax": 255,
                },
                "result": True,
            },
        }
    }

    result = execute_apply_process(process_callback=process_callback)
    expected_data = [[[[140.25, 146.625], [146.625, 153]], [[133.875, 140.25], [12.75, 133.875]]]]
    expected_result = generate_data(data=expected_data)
    assert_equal(result, expected_result)


def test_callback_lsr(execute_apply_process, generate_data):
    """
    Test apply process with linear_scale_range
    """
    process_callback = {
        "process_graph": {
            "lsr": {
                "process_id": "linear_scale_range",
                "arguments": {
                    "x": {"from_parameter": "x"},
                    "inputMin": -3,
                    "inputMax": 3,
                    "outputMin": 0,
                    "outputMax": 1,
                },
                "result": True,
            }
        }
    }

    data_arguments = {"data": [np.nan, -3, 3, 0, np.nan], "dims": ("t")}
    result = execute_apply_process(data_arguments=data_arguments, process_callback=process_callback)
    expected_result = generate_data(data=[np.nan, 0, 1, 0.5, np.nan], dims=("t"))
    assert_equal(result, expected_result)


def test_multiple_results_forbidden(execute_apply_process, generate_data):
    """
    Test apply process with linear_scale_range
    """
    process_callback = {
        "process_graph": {
            "lsr": {
                "process_id": "linear_scale_range",
                "arguments": {
                    "x": {"from_parameter": "x"},
                    "inputMin": -3,
                    "inputMax": 3,
                    "outputMin": 0,
                    "outputMax": 1,
                },
                "result": True,
            },
            "lsr2": {
                "process_id": "linear_scale_range",
                "arguments": {
                    "x": {"from_parameter": "x"},
                    "inputMin": -3,
                    "inputMax": 3,
                    "outputMin": 0,
                    "outputMax": 1,
                },
                "result": True,
            },
        },
    }

    data_arguments = {"data": [np.nan, -3, 3, 0, np.nan], "dims": ("t")}

    with pytest.raises(ProcessParameterInvalid) as ex:
        result = execute_apply_process(data_arguments=data_arguments, process_callback=process_callback)
    assert ex.value.args == (
        "linear_scale_range",
        "result",
        "Only one node in a (sub)graph can have result set to true.",
    )
