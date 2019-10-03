import pytest
import sys, os
import responses
import xarray as xr
import re
import json
import datetime
import boto3

os.environ["DATA_AWS_S3_ENDPOINT_URL"] = "http://minio:9000"

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessArgumentInvalid
FIXTURES_FOLDER = os.path.join(os.path.dirname(__file__), 'fixtures')

@pytest.fixture
def save_resultEOTask():
    return process.save_result.save_resultEOTask(None, "random_job_id", None)

@pytest.fixture
def fake_bbox():
    class BBox:
        def get_lower_left(self):
            return (12.32271,42.06347)

        def get_upper_right(self):
            return (12.33572,42.07112)

    return BBox()

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
def data(fake_bbox):
    band_aliases = {
        "nir": "B08",
        "red": "B04",
    }

    xrdata = xr.DataArray(
        [[[[0.2]]]],
        dims=('t','y', 'x', 'band'),
        coords={
            'band': ["ndvi"],
            't': [datetime.datetime.now()]
        },
        attrs={
            "band_aliases": band_aliases,
            "bbox": fake_bbox,
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