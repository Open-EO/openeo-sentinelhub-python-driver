import pytest
import sys, os
import xarray as xr
import datetime
import logging
import multiprocessing
import numpy as np

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
def execute_apply_process(generate_data):
    logger = multiprocessing.log_to_stderr()
    logger.setLevel(logging.DEBUG)
    def wrapped(data_arguments={}, process=None, logger=logger):
        arguments = {}
        if data_arguments is not None: arguments["data"] = generate_data(**data_arguments)
        if process is not None: arguments["process"] = process

        return process.apply.applyEOTask(None, "" , logger).process(arguments)
    return wrapped


###################################
# tests:
###################################

@pytest.mark.skip(reason="linear_scale_range must be merged")
def test_recursive_callback(execute_apply_process, generate_data):
    """
        Test apply process with a recursive callback, which applies linear_scale_range multiple times
    """
    process = {
        "callback": {
            "p1": {
              "process_id": "apply",
              "arguments": {
                "data": {"from_argument": "data"},
                "process": {
                  "callback": {
                    "p1": {
                        "process_id": "apply",
                        "arguments": {
                            "data": {"from_argument": "data"},
                            "process": {
                                "callback": {
                                    "lsr": {
                                        "process_id": "linear_scale_range",
                                        "arguments": {
                                            "x": {"from_argument": "x"},
                                            "inputMin": -1,
                                            "inputMax": 1,
                                            "outputMax": 1000
                                        },
                                        "result": True
                                    }
                                }
                            }
                        }
                    },
                    "lsr": {
                      "process_id": "linear_scale_range",
                      "arguments": {
                        "x": {"from_node": "p1"},
                        "inputMin": 0,
                        "inputMax": 1000,
                        "outputMin": -1000
                      },
                      "result": True
                    }
                  }
                }
              }
            },
            "lsr": {
              "process_id": "linear_scale_range",
              "arguments": {
                "x": {"from_node": "p1"},
                "inputMin": -1000,
                "inputMax": 1,
                "outputMin": 0,
                "outputMax": 255
              },
              "result": True
            }
        }
    }

    result = execute_apply_process(process=process)
    # expected_data1 = [[[[550, 575], [575, 600]], [[525, 550], [50, 525]]]]
    # expected_data2 = [[[[-449.45, -424.425], [-424.425, -399.4]], [[-474.475, -449.45], [-949.95, -474.475]]]] # I didn't make this easy for myself
    expected_data = [[[[140.25, 146.625], [146.625, 153]], [[133.875, 140.25], [12.75, 133.875]]]]
    expected_result = generate_data(data=expected_data)
    xr.testing.assert_allclose(result, expected_result)


@pytest.mark.skip(reason="linear_scale_range must be merged")
def test_callback_lsr(execute_apply_process, generate_data):
    """
        Test apply process with linear_scale_range
    """
    process = {
        "callback": {
            "lsr": {
              "process_id": "linear_scale_range",
              "arguments": {
                "x": {"from_argument": "x"},
                "inputMin": -3,
                "inputMax": 3,
                "outputMin": 0,
                "outputMax": 1
              },
              "result": True
            }
        }
    }

    data_arguments={"data": [np.nan,-3,3,0,np.nan], "dims": ('t')}
    result = execute_apply_process(data_arguments=data_arguments, process=process)
    expected_result = generate_data(data=[np.nan,0,1,0.5,np.nan], dims=('t'))
    xr.testing.assert_allclose(result, expected_result)