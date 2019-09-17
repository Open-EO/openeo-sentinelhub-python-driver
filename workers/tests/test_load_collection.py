import json
import pytest
import re
import urllib.parse as urlparse
import responses
import json
from copy import deepcopy
import sys, os

os.environ["SENTINELHUB_INSTANCE_ID"] = "fake_sentinel_hub_instance_id"
os.environ["SENTINELHUB_LAYER_ID"] = "S2L1C"

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import InvalidInputError
FIXTURES_FOLDER = os.path.join(os.path.dirname(__file__), 'fixtures')


###################################
# utility methods:
###################################


def assert_wms_bbox_matches(wms_params, crs, west, east, north, south):
    assert wms_params['srsname'] == crs
    assert wms_params['bbox'] == '{south},{west},{north},{east}'.format(west=west, east=east, north=north, south=south)


def query_params_from_url(url):
    parsed = urlparse.urlparse(url)
    unprocessed_params = urlparse.parse_qs(parsed.query)
    result = {}
    for k in unprocessed_params:
        result[k.lower()] = unprocessed_params[k][0]
    return result

def modify_value(data,key,value):
    data2 = deepcopy(data)
    data2[key] = value
    return data2


###################################
# fixtures:
###################################


@pytest.fixture
def response_01():
    filename = os.path.join(FIXTURES_FOLDER, 'response_load_collection01.json')
    assert os.path.isfile(filename), "Please run tests/fixtures/load_fixtures.sh!"
    return json.load(open(filename))

@pytest.fixture
def response_02():
    filename = os.path.join(FIXTURES_FOLDER, 'response_load_collection02.tiff')
    assert os.path.isfile(filename), "Please run tests/fixtures/load_fixtures.sh!"
    return open(filename, 'rb').read()



###################################
# tests:
###################################

@responses.activate
def test_process_load_collection(response_01, response_02):
    """
        Test load_collection process
    """

    sh_url_regex01 = re.compile('^.*sentinel-hub.com/ogc/wfs/.*$')
    responses.add(
        responses.GET,
        sh_url_regex01,
        body=json.dumps(response_01),
        match_querystring=True,
        status=200,
    )

    sh_url_regex02 = re.compile('^.*sentinel-hub.com/ogc/wcs/.*$')
    responses.add(
        responses.GET,
        sh_url_regex02,
        body=response_02,
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

    assert False

    load_collection = process.load_collection.load_collectionEOTask(data, "", None)

    #####################################################################
    result = load_collection.process(data)
    assert len(responses.calls) == 2
    params = query_params_from_url(responses.calls[0].request.url)
    assert_wms_bbox_matches(params, 'EPSG:4326', **bbox)
    #####################################################################

    with pytest.raises(Exception) as ex:
        # Fail if wrong collection id
        args = modify_value(data, "id", "non-existent")
        result = load_collection.process(args)
    assert ex.value.args[0] == "Unknown collection id!"

    with pytest.raises(InvalidInputError) as ex:
        # Fail if incorrect temporal_extent
        args = modify_value(data,"temporal_extent",[None,None])
        result = load_collection.process(args)



