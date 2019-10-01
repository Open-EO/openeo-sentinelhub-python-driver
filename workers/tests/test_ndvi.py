import pytest
import json
import sys, os
import xarray as xr

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessArgumentInvalid
FIXTURES_FOLDER = os.path.join(os.path.dirname(__file__), 'fixtures')


###################################
# fixtures:
###################################


@pytest.fixture
def data():

    band_aliases = {
        "nir": "B08",
        "red": "B04",
    }

    xrdata = xr.DataArray(
        masked_data,
        dims=('t', 'y', 'x', 'band'),
        coords={
            'band': INPUT_BANDS,
            't': patch.timestamp,
        },
        attrs={
            "band_aliases": band_aliases,
            "bbox": bbox,
        },
    )
    return xrdata

@pytest.fixture
def ndviEOTask(arguments):
    return process.load_collection.ndviEOTask(None, "", None)


###################################
# tests:
###################################


@responses.activate
def test_correct(data, ndviEOTask):
    """
        Test ndvi process with correct parameters
    """
    print(data["band_aliases"])
    result = ndviEOTask.process(data)
    assert len(responses.calls) == 2
    params = query_params_from_url(responses.calls[1].request.url)
    assert_wcs_bbox_matches(params, 'EPSG:4326', **arguments["spatial_extent"])