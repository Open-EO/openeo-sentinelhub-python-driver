import os
import datetime
import numpy as np
import xarray as xr
from sentinelhub import CustomUrlParam, BBox, CRS
from sentinelhub.constants import AwsConstants
from eolearn.core import FeatureType, EOPatch
from eolearn.io import S2L1CWCSInput, S1IWWCSInput


from ._common import ProcessEOTask, ProcessArgumentInvalid, Internal


SENTINELHUB_INSTANCE_ID = os.environ.get('SENTINELHUB_INSTANCE_ID', None)
SENTINELHUB_LAYER_ID = os.environ.get('SENTINELHUB_LAYER_ID', None)
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
        patch = None
        INPUT_BANDS = None
        band_aliases = {}
        temporal_extent = _clean_temporal_extent(arguments['temporal_extent'])

        if arguments['id'] == 'S2L1C':
            INPUT_BANDS = AwsConstants.S2_L1C_BANDS
            try:
                patch = S2L1CWCSInput(
                    instance_id=SENTINELHUB_INSTANCE_ID,
                    layer=SENTINELHUB_LAYER_ID,
                    feature=(FeatureType.DATA, 'BANDS'), # save under name 'BANDS'
                    custom_url_params={
                        # custom url for specific bands:
                        CustomUrlParam.EVALSCRIPT: 'return [{}];'.format(", ".join(INPUT_BANDS)),
                    },
                    resx='10m', # resolution x
                    resy='10m', # resolution y
                    maxcc=1.0, # maximum allowed cloud cover of original ESA tiles
                ).execute(EOPatch(), time_interval=temporal_extent, bbox=bbox)
            except Exception as ex:
                raise Internal("Server error: EOPatch creation failed: {}".format(str(ex)))

            band_aliases = {
                "nir": "B08",
                "red": "B04",
            }

        elif arguments['id'] == 'S1GRDIW':
            # SENTINELHUB_LAYER_ID_S1GRD = os.environ.get('SENTINELHUB_LAYER_ID_S1GRD', None)
            print(SENTINELHUB_LAYER_ID_S1GRD)
            print(SENTINELHUB_INSTANCE_ID)
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
            res = '10m'
            try:
                patch = S1IWWCSInput(
                    instance_id=SENTINELHUB_INSTANCE_ID,
                    layer=SENTINELHUB_LAYER_ID_S1GRD,
                    feature=(FeatureType.DATA, 'BANDS'), # save under name 'BANDS'
                    custom_url_params={
                        CustomUrlParam.EVALSCRIPT: 'return [{}];'.format(", ".join(INPUT_BANDS)),
                    },
                    resx='10m', # resolution x
                    resy='10m', # resolution y
                    maxcc=1.0, # maximum allowed cloud cover of original ESA tiles
                ).execute(EOPatch(), time_interval=temporal_extent, bbox=bbox)
            except Exception as ex:
                raise Internal("Server error: EOPatch creation failed: {}".format(str(ex)))
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
                'band': INPUT_BANDS,
                't': patch.timestamp,
            },
            attrs={
                "band_aliases": band_aliases,
                "bbox": bbox,
            },
        )
        return xrdata
