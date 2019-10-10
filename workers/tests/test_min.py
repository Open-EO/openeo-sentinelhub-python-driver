import pytest
import sys, os
import xarray as xr
import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessArgumentInvalid, ProcessArgumentRequired

FIXTURES_FOLDER = os.path.join(os.path.dirname(__file__), 'fixtures')


@pytest.fixture
def minEOTask():
    return process.min.minEOTask(None, "" , None)


@pytest.fixture
def generate_data():
    def _construct(
            ymin = 12.32271,
            ymax = 12.33572,
            xmin = 42.06347,
            xmax = 42.07112,
            data = [[[[0.2,0.8]]]],
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
        attrs = {"band_aliases": band_aliases, "bbox": fake_bbox, **attrs}

        xrdata = xr.DataArray(
            data,
            dims=dims,
            coords=coords,
            attrs=attrs,
        )

        return xrdata
    return _construct

@pytest.fixture
def execute_min_process(generate_data, minEOTask):
    def wrapped(data_arguments={}, ignore_nodata=None):
        arguments = {}
        if data_arguments is not None: arguments["data"] = generate_data(**data_arguments)
        if ignore_nodata is not None: arguments["ignore_nodata"] = ignore_nodata

        return minEOTask.process(arguments)
    return wrapped


###################################
# tests:
###################################

def test_correct(execute_min_process):
    """
        Test min process with correct parameters
    """
    result = execute_min_process()
    print(">>>>>>>>>>>>>>>>>>>> Result at the test")
    print(result)