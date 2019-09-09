import os
import numpy as np
import xarray as xr
from sentinelhub import CustomUrlParam, BBox, CRS
from sentinelhub.constants import AwsConstants
from eolearn.core import FeatureType, EOPatch
from eolearn.io import S2L1CWCSInput


from ._common import ProcessEOTask


SENTINELHUB_INSTANCE_ID = os.environ.get('SENTINELHUB_INSTANCE_ID', None)
SENTINELHUB_LAYER_ID = os.environ.get('SENTINELHUB_LAYER_ID', None)


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
        if arguments['id'] == 'S2L1C':
            INPUT_BANDS = AwsConstants.S2_L1C_BANDS
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
            ).execute(EOPatch(), time_interval=arguments['temporal_extent'], bbox=bbox)
            band_aliases = {
                "nir": "B08",
                "red": "B04",
            }
        else:
            raise Exception("Unknown collection id!")


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