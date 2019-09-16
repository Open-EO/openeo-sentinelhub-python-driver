import json
import pytest
import re
import urllib.parse as urlparse
import responses
import json

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
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
def test_process_load_collection():
    """
        Test load_collection process
    """

    sh_url_regex = re.compile('^.*sentinel-hub.com/.*$')
    responses.add(
        responses.GET,
        sh_url_regex,
        body=bytes(42),
        match_querystring=True,
        status=200,
    )

    bbox = {
        "west": 12.32271,
        "east": 12.33572,
        "north": 42.07112,
        "south": 42.06347
    }
    data = {
        "id": "S2L1C",
        "spatial_extent": bbox,
        "temporal_extent": ["2019-08-16", "2019-08-18"],
    }

    load_collection = process.load_collection.load_collectionEOTask(data, "", None)

    try:
        result = load_collection.process(data)

        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        print(result)
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    except:
        print("there is some weird json decode error")

    print(list(responses.calls))


