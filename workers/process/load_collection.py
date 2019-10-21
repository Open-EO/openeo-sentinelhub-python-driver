import os
import datetime
import re
import numpy as np
import xarray as xr
from sentinelhub import CustomUrlParam, BBox, CRS
from sentinelhub.constants import AwsConstants
import sentinelhub.geo_utils
from eolearn.core import FeatureType, EOPatch
from eolearn.io import S2L1CWCSInput, S2L1CWMSInput, S1IWWCSInput, S1IWWMSInput


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
            raise ProcessArgumentInvalid("The argument 'spatial_extent' in process 'load_collection' is invalid: The resulting image size must be below 1000x1000 pixels, but is: {}x{}.".format(width, height))

        patch = None
        INPUT_BANDS = None
        band_aliases = {}
        temporal_extent = _clean_temporal_extent(arguments['temporal_extent'])

        if arguments['id'] == 'S2L1C':
            InputClassWCS = S2L1CWCSInput
            InputClassWMS = S2L1CWMSInput
            INPUT_BANDS = AwsConstants.S2_L1C_BANDS
            DEFAULT_RES = '10m'
            kwargs = dict(
                instance_id=SENTINELHUB_INSTANCE_ID,
                layer=SENTINELHUB_LAYER_ID_S2L1C,
                feature=(FeatureType.DATA, 'BANDS'), # save under name 'BANDS'
                custom_url_params={
                    CustomUrlParam.EVALSCRIPT: 'return [{}];'.format(", ".join(INPUT_BANDS)),
                },
                maxcc=1.0, # maximum allowed cloud cover of original ESA tiles
            )
            band_aliases = {
                "nir": "B08",
                "red": "B04",
            }

        elif arguments['id'] == 'S1GRDIW':
            InputClassWCS = S1IWWCSInput
            InputClassWMS = S1IWWMSInput
            # https://docs.sentinel-hub.com/api/latest/#/data/Sentinel-1-GRD?id=available-bands-and-data
            INPUT_BANDS = ['VV', 'VH']
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
            DEFAULT_RES = '10m'
            kwargs = dict(
                instance_id=SENTINELHUB_INSTANCE_ID,
                layer=SENTINELHUB_LAYER_ID_S1GRD,
                feature=(FeatureType.DATA, 'BANDS'), # save under name 'BANDS'
                custom_url_params={
                    CustomUrlParam.EVALSCRIPT: 'return [{}];'.format(", ".join(INPUT_BANDS)),
                },
                maxcc=1.0, # maximum allowed cloud cover of original ESA tiles
            )
            band_aliases = {}

        else:
            raise ProcessArgumentInvalid("The argument 'id' in process 'load_collection' is invalid: unknown collection id")

        # apply options and choose appropriate SentinelHubOGCInput subclass which supports them:
        options = arguments.get("options", {})
        if options.get("width") or options.get("height"):
            kwargs["width"] = options.get("width", options.get("height"))
            kwargs["height"] = options.get("height", options.get("width"))
            InputClass = InputClassWMS  # WMS knows width/height
        elif options.get("resx") or options.get("resy"):
            kwargs["resx"] = options.get("resx", options.get("resy"))
            kwargs["resy"] = options.get("resy", options.get("resx"))
            InputClass = InputClassWCS  # WCS knows resx/resy
        else:
            kwargs["resx"] = DEFAULT_RES
            kwargs["resy"] = DEFAULT_RES
            InputClass = InputClassWCS

        # fetch the data:
        try:
            patch = InputClass(**kwargs).execute(EOPatch(), time_interval=temporal_extent, bbox=bbox)
        except Exception as ex:
            _raise_exception_based_on_eolearn_message(str(ex))


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
                'band': INPUT_BANDS,
                't': patch.timestamp,
            },
            attrs={
                "band_aliases": band_aliases,
                "bbox": bbox,
            },
        )
        return xrdata
