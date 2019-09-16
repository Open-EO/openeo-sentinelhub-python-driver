import json
import pytest
import re
import urllib.parse as urlparse

import sys, os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '../process'))
from load_collection import load_collectionEOTask


# FIXTURES_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'fixtures')


###################################
# utility methods:
###################################


def assert_wms_bbox_matches(wms_params, crs, west, east, north, south):
    assert wms_params['version'] == '1.1.1'  # for now we only support this version
    assert wms_params['srs'] == crs  # WMS 1.1.1 uses 'srs', WMS 1.3.0 uses 'crs'
    assert wms_params['bbox'] == '{west},{south},{east},{north}'.format(west=west, east=east, north=north, south=south)


def query_params_from_url(url):
    parsed = urlparse.urlparse(url)
    unprocessed_params = urlparse.parse_qs(parsed.query)
    result = {}
    for k in unprocessed_params:
        result[k.lower()] = unprocessed_params[k][0]
    return result


###################################
# fixtures:
###################################


@pytest.fixture
def app_client():
    app.testing = True
    return app.test_client()


# @pytest.fixture
# def s2l1c_truecolor_32x32_png():
#     filename = os.path.join(FIXTURES_FOLDER, 's2l1c_truecolor_32x32.png')
#     assert os.path.isfile(filename), "Please run tests/fixtures/load_fixtures.sh!"
#     return open(filename, 'rb').read()


###################################
# tests:
###################################

# @pytest.mark.skip(reason="The '/result' endpoint has been changed and it is no longer compatible with this test.")
@responses.activate
def test_process_load_collection(app_client, s2l1c_truecolor_32x32_png):
    """
        Test load_collection process
    """
    bbox = {
        "west": 16.1,
        "east": 16.6,
        "north": 48.6,
        "south": 47.2
    }
    data = {
        "process_graph": {
            "loadco1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "S2L1C",
                    "spatial_extent": bbox,
                    "temporal_extent": ["2017-01-01", "2017-02-01"],
                },
                "result": True,
            },
        },
    }

    result = load_collectionEOTask.process(data)

    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    print(result)
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")


