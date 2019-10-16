import pytest
import sys, os
import xarray as xr
import datetime
import logging
import multiprocessing

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessArgumentInvalid, ProcessArgumentRequired


@pytest.fixture
def generate_data():
    def _construct(
            data = [[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]],
            dims = ('t','y', 'x', 'band')
        ):

        xrdata = xr.DataArray(
            data,
            dims=dims
        )

        return xrdata
    return _construct


@pytest.fixture
def execute_reduce_process(generate_data):
    logger = multiprocessing.log_to_stderr()
    logger.setLevel(logging.DEBUG)
    def wrapped(data_arguments={}, dimension="band", reducer=None, target_dimension=None, binary=None, logger=logger):
        arguments = {}
        if data_arguments is not None: arguments["data"] = generate_data(**data_arguments)
        if dimension is not None: arguments["dimension"] = dimension
        if reducer is not None: arguments["reducer"] = reducer
        if target_dimension is not None: arguments["target_dimension"] = target_dimension
        if binary is not None: arguments["binary"] = binary

        return process.reduce.reduceEOTask(None, "" , logger).process(arguments)
    return wrapped


###################################
# tests:
###################################

def test_no_reducer(execute_reduce_process, generate_data):
    """
        Test reduce process without reducer
    """
    with pytest.raises(ProcessArgumentInvalid) as ex:
        result = execute_reduce_process()
    assert ex.value.args[0] == "The argument 'dimension' in process 'reduce' is invalid: Dimension 'band' has more than one value, but reducer is not specified."

    expected_result = generate_data = generate_data(data = [[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]], dims = ('y','x','band'))
    result = execute_reduce_process(dimension="t")
    xr.testing.assert_allclose(result, expected_result)


def test_recursiver_reducer(execute_reduce_process, generate_data):
    """
        Test reduce process with a recursive reducer, which applies min to all dimensions, apart from the last one
    """
    reducer = {
        "callback": {
            "p1": {
              "process_id": "reduce",
              "arguments": {
                "data": {"from_argument": "data"},
                "dimension": "x",
                "reducer": {
                  "callback": {
                    "p1": {
                        "process_id": "reduce",
                        "arguments": {
                            "data": {"from_argument": "data"},
                            "dimension": "band",
                            "reducer": {
                                "callback": {
                                    "min": {
                                        "process_id": "min",
                                        "arguments": {
                                            "data": {"from_argument": "data"}
                                        },
                                        "result": True
                                    }
                                }
                            }
                        }
                    },
                    "min": {
                      "process_id": "min",
                      "arguments": {
                        "data": {"from_node": "p1"}
                      },
                      "result": True
                    }
                  }
                }
              }
            },
            "min": {
              "process_id": "min",
              "arguments": {
                "data": {"from_node": "p1"}
              },
              "result": True
            }
        }
    }

    result = execute_reduce_process(reducer=reducer, dimension="y")
    expected_result = generate_data(data = [-0.9], dims = ('t'))
    xr.testing.assert_allclose(result, expected_result)


def test_reducer_sum_of_min_and_mean(execute_reduce_process, generate_data):
    """
        Test reduce process with a reducer, which takes min and mean of bands and sums it up
    """
    reducer = {
        "callback": {
            "min": {
              "process_id": "min",
              "arguments": {
                "data": {"from_argument": "data"}
              },
            },
            "mean": {
              "process_id": "mean",
              "arguments": {
                "data": {"from_argument": "data"}
              },
            },
            "sum": {
              "process_id": "sum",
              "arguments": {
                "data": [{"from_node": "min"},{"from_node": "mean"}]
              },
              "result": True
            }
        }
    }

    result = execute_reduce_process(reducer=reducer, dimension="band")
    expected_result = generate_data(data = [[[0.225, 0.325], [0.125, -1.325]]], dims = ('t','y','x'))
    xr.testing.assert_allclose(result, expected_result)


def test_min_time_dim(execute_reduce_process, generate_data):
    """
        Test reduce process with a reducer, which applies min to the temporal dimension
    """
    reducer = {
        "callback": {
            "min": {
              "process_id": "min",
              "arguments": {
                "data": {"from_argument": "data"}
              },
              "result": True
            }
        }
    }

    data_arguments = {"data": [[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]],[[[0.7, 0.05], [-0.009, -0.2]], [[0.05, 0.1], [-0.9, 0.07]]]]}
    result = execute_reduce_process(reducer=reducer, dimension="t", data_arguments=data_arguments)
    expected_result = generate_data(data=[[[0.1, 0.05], [-0.009, -0.2]], [[0.05, 0.1], [-0.9, 0.05]]], dims=('y','x','band'))
    xr.testing.assert_allclose(result, expected_result)
