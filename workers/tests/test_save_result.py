import pytest
import sys, os
import responses
import xarray as xr
import re
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessArgumentInvalid
FIXTURES_FOLDER = os.path.join(os.path.dirname(__file__), 'fixtures')


###################################
# fixtures:
###################################

# @pytest.fixture
# def response_01():
#     filename = os.path.join(FIXTURES_FOLDER, 'response_load_collection01.json')
#     assert os.path.isfile(filename), "Please run load_fixtures.sh!"
#     return json.load(open(filename))

# @pytest.fixture
# def response_02():
#     filename = os.path.join(FIXTURES_FOLDER, 'response_load_collection02.tiff')
#     assert os.path.isfile(filename), "Please run load_fixtures.sh!"
#     return open(filename, 'rb').read()

@pytest.fixture
def save_resultEOTask():
    return process.save_result.save_resultEOTask(None, "random_job_id", None)

@pytest.fixture
def set_responses():
    sh_url_regex01 = re.compile('.')
    responses.add(
        responses.GET,
        sh_url_regex01,
        body=json.dumps({"code":200}),
        match_querystring=True,
        status=200,
    )

    responses.add(
        responses.POST,
        sh_url_regex01,
        body=json.dumps({"code":200}),
        match_querystring=True,
        status=200,
    )

@pytest.fixture
def data():
    band_aliases = {
        "nir": "B08",
        "red": "B04",
    }

    xrdata = xr.DataArray(
        [[[0.2]]],
        dims=('y', 'x', 'band'),
        coords={
            'band': ["ndvi"],
        },
        attrs={
            "band_aliases": band_aliases,
            "bbox": "",
        },
    )

    return xrdata



###################################
# tests:
###################################

@responses.activate
def test_correct(save_resultEOTask, set_responses, data):
    """
        Test save_result process with correct parameters
    """
    arguments = {"data":data,"format":"gtiff"}
    result = save_resultEOTask.process(arguments)
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    print(responses.calls)
    # assert len(responses.calls) == 2
    # params = query_params_from_url(responses.calls[1].request.url)
    # assert_wcs_bbox_matches(params, 'EPSG:4326', **arguments["spatial_extent"])