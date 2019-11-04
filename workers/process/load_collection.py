import os
import datetime
import time
import re
import numpy as np
import xarray as xr
import requests
from osgeo import gdal
from sentinelhub import WmsRequest, WcsRequest, MimeType, CRS, BBox, CustomUrlParam
from sentinelhub.constants import AwsConstants
from sentinelhub.config import SHConfig
import sentinelhub.geo_utils
from eolearn.core import FeatureType, EOPatch


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


class SHProcessingAuthTokenSingleton(object):
    _access_token = None
    _valid_until = None

    @classmethod
    def get(cls):
        if cls._access_token is not None and cls._valid_until > time.time():
            return cls._access_token

        client_id = os.environ.get('SH_CLIENT_ID')
        auth_secret = os.environ.get('SH_AUTH_SECRET')
        if not client_id or not auth_secret:
            raise Internal("Missing SH credentials")

        url = 'https://services.sentinel-hub.com/oauth/token'
        data = f'grant_type=client_credentials&client_id={client_id}&client_secret={auth_secret}'
        r = requests.post(url, headers={'Content-Type': 'application/x-www-form-urlencoded'}, data=data)
        if r.status_code != 200:
            raise Internal("Error authenticating, received code: " + str(r.status_code))

        j = r.json()
        cls._access_token = j["access_token"]
        cls._valid_until = time.time() + j["expires_in"] - 5
        return cls._access_token


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
        options = arguments.get("options", {})
        if not (options.get("width") or options.get("height")):
            width, height = sentinelhub.geo_utils.bbox_to_dimensions(bbox, 10.0)
            if width * height > 1000 * 1000:
                raise ProcessArgumentInvalid("The argument 'spatial_extent' in process 'load_collection' is invalid: The resulting image size must be below 1000x1000 pixels, but is: {}x{}.".format(width, height))

        bands = arguments.get("bands")
        if bands is not None:
            if not isinstance(bands, list):
                raise ProcessArgumentInvalid("The argument 'bands' in process 'load_collection' is invalid: Argument must be a list.")
            if not len(bands):
                raise ProcessArgumentInvalid("The argument 'bands' in process 'load_collection' is invalid: At least one band must be specified.")

        band_aliases = {}
        temporal_extent = _clean_temporal_extent(arguments['temporal_extent'])

        if arguments['id'] == 'S2L1C':
            dataset = "S2L1C"
            ALL_BANDS = AwsConstants.S2_L1C_BANDS
            bands = validate_bands(bands, ALL_BANDS, arguments['id'])
            DEFAULT_RES = '10m'
            kwargs = dict(
                layer=SENTINELHUB_LAYER_ID_S2L1C,
                maxcc=1.0, # maximum allowed cloud cover of original ESA tiles
            )
            band_aliases = {
                "nir": "B08",
                "red": "B04",
            }

        elif arguments['id'] == 'S1GRDIW':
            dataset = "S1GRD"
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
            DEFAULT_RES = '10m'
            kwargs = dict(
                layer=SENTINELHUB_LAYER_ID_S1GRD,
            )
            band_aliases = {}

        else:
            raise ProcessArgumentInvalid("The argument 'id' in process 'load_collection' is invalid: unknown collection id")

        self.logger.debug(f'Requesting dates between: ...')
        request = WmsRequest(
            # **kwargs,
            layer=SENTINELHUB_LAYER_ID_S2L1C,
            maxcc=1.0, # maximum allowed cloud cover of original ESA tiles
            instance_id=SENTINELHUB_INSTANCE_ID,
            bbox=bbox,
            time=temporal_extent,
            # time=['2019-08-01T00:00:00+00:00', '2019-08-18T23:59:00+00:00'],
            # time=('2019-08-01', '2019-08-18'),
            width=256,
            height=256,
        )
        dates = request.get_dates()
        unique_dates = sorted(list(set([d.strftime("%Y-%m-%d") for d in dates])))

        self.logger.debug(f'Unique dates found: {unique_dates}')
        response_data = np.empty((len(unique_dates), len(bands) + 1, 256, 256), dtype=np.float32)
        auth_token = SHProcessingAuthTokenSingleton.get()
        url = 'https://services.sentinel-hub.com/api/v1/process'
        headers = {
            'Accept': 'image/tiff',
            'Authorization': f'Bearer {auth_token}'
        }
        for i, date in enumerate(unique_dates):
            request_params = {
                "input": {
                    "bounds": {
                        "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
                        "properties": {
                            "crs": "http://www.opengis.net/def/crs/EPSG/0/4326",
                        }
                    },
                    "data": [
                        {
                            "type": dataset,
                            "dataFilter": {
                                "timeRange": {
                                    "from": f"{date}T00:00:00+00:00",
                                    "to": f"{date}T23:59:59+00:00",
                                },
                                "previewMode": "EXTENDED_PREVIEW",
                            }
                        },
                    ],
                },
                "output": {
                    "width": options.get("width", options.get("height", 256)),
                    "height": options.get("height", options.get("width", 256)),
                },
                "evalscript": f"""//VERSION=3

                    function setup() {{
                        return {{
                            input: [{', '.join([f'"{b}"' for b in bands])}],
                            output: {{
                                bands: {len(bands) + 1},
                                sampleType: "FLOAT32",
                            }}
                        }}
                    }}

                    function evaluatePixel(sample) {{
                        return [{", ".join(['sample.' + b for b in bands])}, sample.dataMask]
                    }}
                """
            }
            self.logger.debug(f'Requesting tiff for: {date}')
            r = requests.post(url, headers=headers, json=request_params)
            if r.status_code != 200:
                raise Internal(r.content)

            # convert tiff to numpy:
            tmp_filename = f'/tmp/test.{self.job_id}.tiff'
            with open(tmp_filename, 'wb') as f:
                f.write(r.content)
                f.close()
            raster_ds = gdal.Open(tmp_filename, gdal.GA_ReadOnly)
            image_gdal = raster_ds.ReadAsArray()
            os.remove(tmp_filename)

            response_data[i, ...] = image_gdal
            self.logger.debug('Image received and converted.')

        # data is arranged differently than it was with sentinelhub-py,
        # let's rearrange it:
        response_data = np.transpose(response_data, (0, 2, 3, 1))

        # split mask (IS_DATA) from the data itself:
        rd = np.asarray(response_data)
        mask = rd[:, :, :, -1].astype(bool)
        data = rd[:, :, :, :-1]
        # use MaskedArray:
        masked_data = data.view(np.ma.MaskedArray)
        masked_data[~mask] = np.ma.masked

        xrdata = xr.DataArray(
            masked_data,
            dims=('t', 'y', 'x', 'band'),
            coords={
                'band': bands,
                't': unique_dates,
            },
            attrs={
                "band_aliases": band_aliases,
                "bbox": bbox,
            },
        )
        return xrdata
