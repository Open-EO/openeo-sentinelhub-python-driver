import pytest
import sys, os
import xarray as xr
import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessArgumentInvalid, ProcessArgumentRequired

FIXTURES_FOLDER = os.path.join(os.path.dirname(__file__), 'fixtures')


@pytest.fixture
def reduceEOTask():
    return process.reduce.reduceEOTask(None, "" , None)


@pytest.fixture
def generate_data():
    def _construct(
            ymin = 12.32271,
            ymax = 12.33572,
            xmin = 42.06347,
            xmax = 42.07112,
            data = [[[[0.1, 0.15], [0.15, 0.2]], [[0.05, 0.1], [-0.9, 0.05]]]],
            dims = ('t','y', 'x', 'band'),
            coords = {'band': ["B04","B08"],'t': [datetime.datetime.now()]},
            band_aliases = { "nir": "B08", "red": "B04"},
            attrs = {}
        ):
        class BBox:
            def get_lower_left(self):
                return (ymin,xmin)

            def get_upper_right(self):
                return (ymax,xmax)

        fake_bbox = BBox()
        attrs = {"band_aliases": band_aliases, "bbox": fake_bbox,  **attrs}

        xrdata = xr.DataArray(
            data,
            dims=dims,
            coords=coords,
            attrs=attrs,
        )

        return xrdata
    return _construct

@pytest.fixture
def reducer_recursive():
    return {
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


@pytest.fixture
def execute_reduce_process(generate_data, reduceEOTask):
    def wrapped(data_arguments={}, dimension="band", reducer=None, target_dimension=None, binary=None):
        arguments = {}
        if data_arguments is not None: arguments["data"] = generate_data(dimension, **data_arguments)
        if dimension is not None: arguments["dimension"] = dimension
        if reducer is not None: arguments["reducer"] = reducer
        if target_dimension is not None: arguments["target_dimension"] = target_dimension
        if binary is not None: arguments["binary"] = binary

        return reduceEOTask.process(arguments)
    return wrapped


###################################
# tests:
###################################

def test_no_reducer(execute_reduce_process):
    """
        Test reduce process without reducer
    """
    with pytest.raises(ProcessArgumentInvalid) as ex:
        result = execute_reduce_process()
    # print(">>>>>>>>>>>>>>>>>>>> Result at the test\n")
    # print(result)

def test_recursiver_reducer(execute_reduce_process,reducer_recursive):
    result = execute_reduce_process(reducer=reducer_recursive, dimension="y")
    print(">>>>>>>>>>>>>>>>>>>> Result at the test with reducer:\n")
    print(result)
