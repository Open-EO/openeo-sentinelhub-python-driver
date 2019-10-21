import os
import datetime
import re
import numpy as np
import xarray as xr
from sentinelhub import CustomUrlParam, BBox, CRS
from sentinelhub.constants import AwsConstants
import sentinelhub.geo_utils
from eolearn.core import FeatureType, EOPatch
from eolearn.io import S2L1CWCSInput, S1IWWCSInput


from ._common import ProcessEOTask, ProcessArgumentInvalid, Internal


SENTINELHUB_INSTANCE_ID = os.environ.get('SENTINELHUB_INSTANCE_ID', None)
SENTINELHUB_LAYER_ID_S2L1C = os.environ.get('SENTINELHUB_LAYER_ID_S2L1C', None)
SENTINELHUB_LAYER_ID_S1GRD = os.environ.get('SENTINELHUB_LAYER_ID_S1GRD', None)


def _clean_temporal_extent(temporal_extent):
    """
        EOLearn expects the date strings not to include `Z` at the end, so we
        fix input here. It also doesn't deal with None, so we fix this.
        Note that this implementation is still not 100% correct, because we should
        also be accepting strings with *only time* for example.
        https://eo-learn.readthedocs.io/en/latest/eolearn.io.sentinelhub_service.html#eolearn.io.sentinelhub_service.SentinelHubOGCInput.execute
    """

    # Check that only one of the intervals is None: (if any)
    # https://open-eo.github.io/openeo-api/processreference/#load_collection
    # > Also supports open intervals by setting one of the boundaries to null, but never both.
    if temporal_extent == [None, None]:
        raise ProcessArgumentInvalid("The argument 'temporal_extent' in process 'load_collection' is invalid: Only one boundary can be set to null.")
    if not isinstance(temporal_extent,list) or len(temporal_extent) != 2:
        raise ProcessArgumentInvalid("The argument 'temporal_extent' in process 'load_collection' is invalid: The interval has to be specified as an array with exactly two elements.")

    result = [None if t is None else t.rstrip('Z') for t in temporal_extent]
    if result[0] is None:
        result[0] = '1970-01-01'
    if result[1] is None:
        # result[1] = 'latest'  # currently this doesn't work
        result[1] = datetime.datetime.utcnow().isoformat()
    return result


def _raise_exception_based_on_eolearn_message(str_ex):
    # EOLearn raises an exception which doesn't have the original data anymore, so we must
    # parse the message to figure out if the error was 4xx or 5xx.
    r = re.compile(r'Failed to download from:\n([^\n]+)\nwith ([^:]+):\n([4-5][0-9]{2}) ([^:]+): (.*)')
    m = r.match(str_ex)
    if m:
        g = m.groups()
        status_code = int(g[2])
        if 400 <= status_code < 500:
            raise ProcessArgumentInvalid(f"The argument '<unknown>' in process 'load_collection' is invalid: {str_ex}")

    # we can't make sense of the message, bail out with generic exception:
    raise Internal("Server error: EOPatch creation failed: {}".format(str_ex))

def validate_bands(bands, ALL_BANDS, collection_id):
    if bands is None:
        return ALL_BANDS
    if not set(bands).issubset(ALL_BANDS):
        valids = ",".join(ALL_BANDS)
        raise ProcessArgumentInvalid("The argument 'bands' in process 'load_collection' is invalid: Invalid bands encountered; valid bands for {} are '[{}]'.".format(collection_id,valids))
    return bands


class load_collectionEOTask(ProcessEOTask):
    @staticmethod
    def _convert_bbox(spatial_extent):
        crs = spatial_extent.get('crs', 4326)
        return BBox(
            (spatial_extent['west'],
            spatial_extent['south'],
            spatial_extent['east'],
            spatial_extent['north'],),
            CRS(crs),  # we support whatever sentinelhub-py supports
        )


    def process(self, arguments):
        spatial_extent = arguments['spatial_extent']
        bbox = load_collectionEOTask._convert_bbox(spatial_extent)

        # check if the bbox is within the allowed limits:
        width, height = sentinelhub.geo_utils.bbox_to_dimensions(bbox, 10.0)
        if width * height > 1000 * 1000:
            raise ProcessArgumentInvalid("The argument 'spatial_extent' in process 'load_collection' is invalid: The resulting image size must be below 1000x1000 pixels.")

        bands = arguments.get("bands")

        if bands is not None:
            if not isinstance(bands, list):
                raise ProcessArgumentInvalid("The argument 'bands' in process 'load_collection' is invalid: Argument must be a list.")
            if not len(bands):
                raise ProcessArgumentInvalid("The argument 'bands' in process 'load_collection' is invalid: At least one band must be specified.")

        band_aliases = {}
        temporal_extent = _clean_temporal_extent(arguments['temporal_extent'])

        patch = EOPatch()

        if arguments['id'] == 'S2L1C':
            ALL_BANDS = AwsConstants.S2_L1C_BANDS
            bands = validate_bands(bands, ALL_BANDS, arguments['id'])

            try:
                patch = S2L1CWCSInput(
                    instance_id=SENTINELHUB_INSTANCE_ID,
                    layer=SENTINELHUB_LAYER_ID_S2L1C,
                    feature=(FeatureType.DATA, 'BANDS'), # save under name 'BANDS'
                    custom_url_params={
                        # custom url for specific bands:
                        CustomUrlParam.EVALSCRIPT: 'return [{}];'.format(",".join(bands)),
                    },
                    resx='10m', # resolution x
                    resy='10m', # resolution y
                    maxcc=1.0, # maximum allowed cloud cover of original ESA tiles
                ).execute(patch, time_interval=temporal_extent, bbox=bbox)
            except Exception as ex:
                _raise_exception_based_on_eolearn_message(str(ex))

            band_aliases = {
                "nir": "B08",
                "red": "B04",
            }

        elif arguments['id'] == 'S1GRDIW':
            # https://docs.sentinel-hub.com/api/latest/#/data/Sentinel-1-GRD?id=available-bands-and-data
            ALL_BANDS = ['VV', 'VH']
            bands = validate_bands(bands, ALL_BANDS, arguments['id'])

            # https://docs.sentinel-hub.com/api/latest/#/data/Sentinel-1-GRD?id=resolution-pixel-spacing
            #   Value     Description
            #   HIGH      10m/px for IW and 25m/px for EW
            #   MEDIUM    40m/px for IW and EW
            # https://sentinel-hub.com/develop/documentation/eo_products/Sentinel1EOproducts
            #   Sensing Resolution:
            #     - Medium
            #     - High
            #   Similarly to polarization, not all beam mode/polarization combinations will have data
            #   at the chosen resolution. IW is typically sensed in High resolution, EW in Medium.
            res = '10m'
            try:
                patch = S1IWWCSInput(
                    instance_id=SENTINELHUB_INSTANCE_ID,
                    layer=SENTINELHUB_LAYER_ID_S1GRD,
                    feature=(FeatureType.DATA, 'BANDS'), # save under name 'BANDS'
                    custom_url_params={
                        CustomUrlParam.EVALSCRIPT: 'return [{}];'.format(",".join(bands)),
                    },
                    resx=res,
                    resy=res,
                    maxcc=1.0, # maximum allowed cloud cover of original ESA tiles
                ).execute(patch, time_interval=temporal_extent, bbox=bbox)
            except Exception as ex:
                _raise_exception_based_on_eolearn_message(str(ex))

            band_aliases = {}

        else:
            raise ProcessArgumentInvalid("The argument 'id' in process 'load_collection' is invalid: unknown collection id")


        # apart from all the bands, we also want to have access to "IS_DATA", which
        # will be applied as masked_array:
        data = patch.data["BANDS"]
        mask = patch.mask["IS_DATA"]
        mask = mask.reshape(mask.shape[:-1])  # get rid of last axis
        masked_data = data.view(np.ma.MaskedArray)
        masked_data[~mask] = np.ma.masked

        xrdata = xr.DataArray(
            masked_data,
            dims=('t', 'y', 'x', 'band'),
            coords={
                'band': bands,
                't': patch.timestamp,
            },
            attrs={
                "band_aliases": band_aliases,
                "bbox": bbox,
            },
        )
        return xrdata
