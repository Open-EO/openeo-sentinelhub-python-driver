import json
import pytest
import re
import urllib.parse as urlparse
import responses
import json
from copy import deepcopy
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessArgumentInvalid
FIXTURES_FOLDER = os.path.join(os.path.dirname(__file__), 'fixtures')


###################################
# utility methods:
###################################


def assert_wcs_bbox_matches(wcs_params, crs, west, east, north, south):
    assert wcs_params['crs'] == crs

    if crs == 'EPSG:4326':
        if wcs_params['version'] == '1.1.2':
            assert wcs_params['bbox'] == '{south},{west},{north},{east}'.format(west=west, east=east, north=north, south=south)
        elif wcs_params['version'] == '1.0.0':
            assert wcs_params['bbox'] == '{west},{south},{east},{north}'.format(west=west, east=east, north=north, south=south)
        else:
            assert False, "The tests do not know how to handle this version!"
    else:
        assert False, "The tests do not know how to handle this CRS!"


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
def arguments_factory():
    def wrapped(
        collection_id,
        temporal_extent=["2019-08-16", "2019-08-18"],
        bbox = {
            "west": 12.32271,
            "east": 12.33572,
            "north": 42.07112,
            "south": 42.06347
        },
    ):
        return {
            "id": collection_id,
            "spatial_extent": bbox,
            "temporal_extent": temporal_extent,
        }
    return wrapped

@pytest.fixture
def argumentsS2L1C(arguments_factory):
    return arguments_factory("S2L1C")

@pytest.fixture
def argumentsS1GRDIW(arguments_factory):
    return arguments_factory("S1GRDIW")

@pytest.fixture
def execute_load_collection_process():
    # While this fixture doesn't use `set_responses` directly, we always want to run this side-effect
    # whenever we execute load_collection prosess, so it makes sense to depend on it here.
    def wrapped(arguments):
        return process.load_collection.load_collectionEOTask(arguments, "", None).process(arguments)
    return wrapped

@pytest.fixture
def set_mock_responses():
    def wrapped(collection_id):
        filename = os.path.join(FIXTURES_FOLDER, f'response_load_collection_{collection_id.lower()}.json')
        assert os.path.isfile(filename), "Please run load_fixtures.sh!"
        responses.add(
            responses.GET,
            re.compile(r'^.*sentinel-hub.com/ogc/wfs/.*$'),
            body=json.dumps(json.load(open(filename))),
            match_querystring=True,
            status=200,
        )

        filename = os.path.join(FIXTURES_FOLDER, f'response_load_collection_{collection_id.lower()}.tiff')
        assert os.path.isfile(filename), "Please run load_fixtures.sh!"
        responses.add(
            responses.GET,
            re.compile(r'^.*sentinel-hub.com/ogc/wcs/.*$'),
            body=open(filename, 'rb').read(),
            match_querystring=True,
            status=200,
        )
    return wrapped


###################################
# tests:
###################################


@pytest.mark.parametrize('collection_id,temporal_extent', [
    ("S2L1C", ["2019-08-16", "2019-08-18"],),
    ("S1GRDIW", ["2019-08-16 00:00:00", "2019-08-17 05:19:11"],),
])
@responses.activate
def test_correct(set_mock_responses, arguments_factory, execute_load_collection_process, collection_id, temporal_extent):
    """
        Test load_collection process with correct parameters (S2L1C, S1GRDIW,...)
    """
    set_mock_responses(collection_id)
    arguments = arguments_factory(collection_id, temporal_extent=temporal_extent)
    result = execute_load_collection_process(arguments)
    assert len(responses.calls) == 2
    params = query_params_from_url(responses.calls[1].request.url)
    assert_wcs_bbox_matches(params, 'EPSG:4326', **arguments["spatial_extent"])


def test_collection_id(arguments_factory, execute_load_collection_process):
    """
        Test load_collection process with incorrect collection id
    """
    arguments = arguments_factory("non-existent")
    with pytest.raises(ProcessArgumentInvalid) as ex:
        result = execute_load_collection_process(arguments)
    assert ex.value.args[0] == "The argument 'id' in process 'load_collection' is invalid: unknown collection id"


@pytest.mark.parametrize('invalid_temporal_extent,failure_reason', [
    ([None,None], "Only one boundary can be set to null."),
    ("A date", "The interval has to be specified as an array with exactly two elements."),
])
def test_temporal_extent_invalid(arguments_factory, execute_load_collection_process, invalid_temporal_extent, failure_reason):
    """
        Test load_collection process with incorrect temporal_extent
    """
    arguments = arguments_factory("S2L1C", temporal_extent = invalid_temporal_extent)
    with pytest.raises(ProcessArgumentInvalid) as ex:
        result = execute_load_collection_process(arguments)
    assert ex.value.args[0] == f"The argument 'temporal_extent' in process 'load_collection' is invalid: {failure_reason}"
