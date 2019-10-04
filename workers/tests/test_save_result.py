import pytest
import sys, os
import xarray as xr
import re
import json
import datetime
from botocore.stub import Stubber,ANY

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessArgumentInvalid
FIXTURES_FOLDER = os.path.join(os.path.dirname(__file__), 'fixtures')

S3_BUCKET_NAME = 'com.sinergise.openeo.results'
DATA_AWS_S3_ENDPOINT_URL = os.environ.get('DATA_AWS_S3_ENDPOINT_URL')
JOB_ID = "random_job_id"

@pytest.fixture
def save_resultEOTask():
    return process.save_result.save_resultEOTask(None, JOB_ID , None)

@pytest.fixture
def gtiff_object():
    filename = os.path.join(FIXTURES_FOLDER, 'gtiff_object.tiff')
    body = open(filename, 'rb').read()
    return body

@pytest.fixture(autouse=True)
def s3_stub(save_resultEOTask):
    client = save_resultEOTask._s3
    with Stubber(client) as stubber:
        yield stubber

@pytest.fixture
def fake_bbox():
    class BBox:
        def get_lower_left(self):
            return (12.32271,42.06347)

        def get_upper_right(self):
            return (12.33572,42.07112)

    return BBox()


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

def test_correct(save_resultEOTask, data, s3_stub, gtiff_object):
    """
        Test save_result process with correct parameters
    """
    s3_stub.add_response(
        'put_object',
        expected_params = {
            'ACL': ANY,
            'Body': gtiff_object,
            'Bucket': S3_BUCKET_NAME,
            'ContentType': ANY,
            'Expires': ANY,
            'Key': ANY
        },
        service_response={},
    )
    
    arguments = {"data":data,"format":"gtiff"}
    result = save_resultEOTask.process(arguments)

    s3_stub.assert_no_pending_responses()
