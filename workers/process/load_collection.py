from datetime import datetime, timedelta
import math
import os
import re
import time

from concurrent.futures import ThreadPoolExecutor
from dask import delayed
import dask.array as da
from eolearn.core import FeatureType, EOPatch
import numpy as np
import imageio
from osgeo import gdal
import requests
from requests_futures.sessions import FuturesSession
from sentinelhub import WmsRequest, WcsRequest, MimeType, CRS, BBox, CustomUrlParam, BBoxSplitter, DataCollection
from sentinelhub.config import SHConfig
from sentinelhub.constants import AwsConstants
import sentinelhub.geo_utils
import xarray as xr

from ._common import ProcessEOTask, ProcessParameterInvalid, Internal, Band


SENTINELHUB_INSTANCE_ID = os.environ.get("SENTINELHUB_INSTANCE_ID", None)
SENTINELHUB_LAYER_ID_S2L1C = os.environ.get("SENTINELHUB_LAYER_ID_S2L1C", None)
SENTINELHUB_LAYER_ID_S2L2A = os.environ.get("SENTINELHUB_LAYER_ID_S2L2A", None)
SENTINELHUB_LAYER_ID_S1GRD = os.environ.get("SENTINELHUB_LAYER_ID_S1GRD", None)


# https://docs.sentinel-hub.com/api/latest/data/sentinel-2-l1c/
S2_L1C_BANDS = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B10", "B11", "B12", "CLP", "CLM", "sunAzimuthAngles", "sunZenithAngles", "viewAzimuthMean", "viewZenithMean"]
# https://docs.sentinel-hub.com/api/latest/data/sentinel-2-l1c/#available-bands-and-data
S2_L1C_WAVELENGTHS = dict(
    zip(S2_L1C_BANDS, [0.4427, 0.4924, 0.5598, 0.6646, 0.7041, 0.7405, 0.7828, 0.8328, 0.8647, 0.9451, 1.3735, 1.6137, 2.2024, None, None, None, None, None, None,])
)
# https://github.com/radiantearth/stac-spec/blob/v0.9.0/extensions/eo/README.md#common-band-names
S2_L1C_ALIASES = dict(
    zip(
        S2_L1C_BANDS,
        ["coastal", "blue", "green", "red", None, None, None, "nir", "nir08", "nir09", "cirrus", "swir16", "swir22", None, None, None, None, None, None,],
    )
)

# https://docs.sentinel-hub.com/api/latest/data/sentinel-2-l2a/
S2_L2A_BANDS = [
    "B01",
    "B02",
    "B03",
    "B04",
    "B05",
    "B06",
    "B07",
    "B08",
    "B8A",
    "B09",
    "B11",
    "B12",
    "AOT",
    "SCL",
    "SNW",
    "CLD",
    "CLP",
    "CLM",
    "sunAzimuthAngles",
    "sunZenithAngles",
    "viewAzimuthMean",
    "viewZenithMean",
    "dataMask"
]
S2_L2A_WAVELENGTHS = dict(
    zip(
        S2_L2A_BANDS,
        [   0.4427,
            0.4924,
            0.5598,
            0.6646, 
            0.7041, 
            0.7405, 
            0.7828, 
            0.8328, 
            0.8647, 
            0.9451, 
            1.6137, 
            2.2024,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ],
    )
)
S2_L2A_ALIASES = dict(
    zip(
        S2_L2A_BANDS,
        [
            "coastal",
            "blue",
            "green",
            "red",
            None,
            None,
            None,
            "nir",
            "nir08",
            "nir09",
            "swir16",
            "swir22",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ],
    )
)

# https://docs.sentinel-hub.com/api/latest/#/data/Sentinel-1-GRD?id=available-bands-and-data
S1_GRD_IW_BANDS = ["VV", "VH"]


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
        raise ProcessParameterInvalid("load_collection", "temporal_extent", "Only one boundary can be set to null.")
    if not isinstance(temporal_extent, list) or len(temporal_extent) != 2:
        raise ProcessParameterInvalid(
            "load_collection",
            "temporal_extent",
            "The interval has to be specified as an array with exactly two elements.",
        )

    result = [None if t is None else t.rstrip("Z") for t in temporal_extent]
    if result[0] is None:
        result[0] = "1970-01-01"
    if result[1] is None:
        # result[1] = 'latest'  # currently this doesn't work
        result[1] = datetime.utcnow().isoformat()
    return result


def _raise_exception_based_on_eolearn_message(str_ex):
    # EOLearn raises an exception which doesn't have the original data anymore, so we must
    # parse the message to figure out if the error was 4xx or 5xx.
    r = re.compile(r"Failed to download from:\n([^\n]+)\nwith ([^:]+):\n([4-5][0-9]{2}) ([^:]+): (.*)")
    m = r.match(str_ex)
    if m:
        g = m.groups()
        status_code = int(g[2])
        if 400 <= status_code < 500:
            raise ProcessParameterInvalid("load_collection", "<unknown>", str_ex)

    # we can't make sense of the message, bail out with generic exception:
    raise Internal("Server error: EOPatch creation failed: {}".format(str_ex))


def validate_bands(bands, ALL_BANDS, collection_id):
    if bands is None:
        return ALL_BANDS
    if not set(bands).issubset(ALL_BANDS):
        valids = ",".join(ALL_BANDS)
        raise ProcessParameterInvalid(
            "load_collection", "bands", f"Invalid bands encountered; valid bands for {collection_id} are '[{valids}]'."
        )
    return bands


def get_orbit_dates(dates):
    """
    We calculate orbit dates by grouping together those dates that are less than an hour apart.
    Returns a list of objects, each with keys "from" and "to", containing datetime structs.
    """
    sorted_dates = sorted(dates)
    result = []
    for d in sorted_dates:
        if len(result) == 0 or d - result[-1]["to"] > timedelta(hours=1):
            result.append({"from": d, "to": d})  # new orbit
        else:
            result[-1]["to"] = d  # same orbit

    return result


def construct_image(data, n_width, n_height):
    rows = []
    for i in range(n_height):
        print(data[i::n_height])
        rows.append(da.concatenate(data[i::n_height], axis=1))
    return da.concatenate(rows[::-1], axis=0)


def download_data(
    self,
    dataset,
    orbit_dates,
    total_width,
    total_height,
    bbox,
    temporal_extent,
    bands,
    dataFilter_params,
    max_chunk_size=1000,
):
    auth_token = self.job_metadata.get("auth_token")
    url = "https://services.sentinel-hub.com/api/v1/process"
    headers = {"Accept": "image/tiff", "Authorization": f"Bearer {auth_token}"}

    n_width = math.ceil(total_width / max_chunk_size)
    n_height = math.ceil(total_height / (max_chunk_size * max_chunk_size / (total_width // n_width + 1)))
    bbox_list = BBoxSplitter([bbox.geometry], CRS.WGS84, (n_width, n_height)).get_bbox_list()
    x_image_shapes = [
        total_width // n_width + 1 if w < total_width % n_width else total_width // n_width for w in range(n_width)
    ]
    y_image_shapes = [
        total_height // n_height + 1 if h < total_height % n_height else total_height // n_height
        for h in range(n_height)
    ]

    adapter_kwargs = dict(pool_maxsize=len(orbit_dates) * n_width * n_height)
    executor = ThreadPoolExecutor(max_workers=len(orbit_dates) * n_width * n_height)
    requests_session = FuturesSession(executor=executor, adapter_kwargs=adapter_kwargs)
    response_futures = {}

    orbit_times_middle, shapes = [], {}

    tmp_folder = f"/tmp-{self.job_id}"
    if os.path.exists(tmp_folder):
        os.rmdir(tmp_folder)
    os.mkdir(tmp_folder)

    for i, date in enumerate(orbit_dates):
        mean_time = date["from"] + (date["to"] - date["from"]) / 2
        tile_from = mean_time - timedelta(minutes=25)
        tile_to = mean_time + timedelta(minutes=25)
        orbit_times_middle.append(mean_time)
        shapes[i] = []

        for j, bbox_section in enumerate(bbox_list):
            request_params = {
                "input": {
                    "bounds": {
                        "bbox": [bbox_section.min_x, bbox_section.min_y, bbox_section.max_x, bbox_section.max_y],
                        "properties": {
                            "crs": "http://www.opengis.net/def/crs/EPSG/0/4326",
                        },
                    },
                    "data": [
                        {
                            "type": dataset,
                            "dataFilter": {
                                "timeRange": {
                                    "from": tile_from.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                                    "to": tile_to.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                                },
                                **dataFilter_params,
                            },
                        },
                    ],
                },
                "output": {
                    "width": x_image_shapes[j // n_height],
                    "height": y_image_shapes[j % n_height],
                },
                "evalscript": f"""//VERSION=3

                    function setup() {{
                        return {{
                            input: [{', '.join([f'"{b}"' for b in bands])}, "dataMask"],
                            output: {{
                                bands: {len(bands) + 1},
                                sampleType: "FLOAT32",
                            }}
                        }}
                    }}

                    function evaluatePixel(sample) {{
                        return [{", ".join(['sample.' + b for b in bands])}, sample.dataMask]
                    }}
                """,
            }
            shapes[i].append((y_image_shapes[j % n_height], x_image_shapes[j // n_height], len(bands) + 1))
            r = requests_session.post(url, headers=headers, json=request_params)
            response_futures[r] = {"date": i, "bbox": j}

    dates_filenames = {}

    for r_future, indices in response_futures.items():
        r = r_future.result()
        if r.status_code != 200:
            # this is not always correct handling: (the error could be triggered by invalid or expired auth token)
            raise Internal(r.content)
        self.logger.debug("Image received.")

        tmp_filename = f'{tmp_folder}/image-{indices["date"]}-{indices["bbox"]}.tiff'
        if dates_filenames.get(indices["date"]) is None:
            dates_filenames[indices["date"]] = [tmp_filename]
        else:
            dates_filenames[indices["date"]].append(tmp_filename)
        with open(tmp_filename, "wb") as f:
            f.write(r.content)

    response_data = []
    for i in range(len(orbit_dates)):
        images = [delayed(imageio.imread)(filename) for filename in dates_filenames[i]]
        images = [da.from_delayed(image, shape=shapes[i][j], dtype=np.float32) for j, image in enumerate(images)]
        image_gdal = construct_image(images, n_width, n_height)
        response_data.append(image_gdal)

    response_data = da.stack(response_data)
    self.logger.debug("Images created.")
    return response_data, orbit_times_middle


def get_collection_times(self, sh_collection_id, bbox, temporal_extent):
    auth_token = self.job_metadata.get("auth_token")
    url = "https://services.sentinel-hub.com/api/v1/catalog/search"
    headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

    request_payload = {
        "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
        "datetime": temporal_extent[0] + "Z/" + temporal_extent[1] + "Z",
        "collections": [sh_collection_id],
    }

    r = requests.post(url, headers=headers, json=request_payload)
    if r.status_code != 200:
        raise Internal("Error retrieving SH catalog, received code: " + str(r.status_code))

    datetimes = []
    for feature in r.json()["features"]:
        datetimes.append(datetime.strptime(feature["properties"]["datetime"], "%Y-%m-%dT%H:%M:%SZ"))

    self.logger.debug(sorted(list(set(datetimes))))
    return sorted(list(set(datetimes)))


class load_collectionEOTask(ProcessEOTask):
    @staticmethod
    def _convert_bbox(spatial_extent):
        crs = spatial_extent.get("crs", 4326)
        return BBox(
            (
                spatial_extent["west"],
                spatial_extent["south"],
                spatial_extent["east"],
                spatial_extent["north"],
            ),
            CRS(crs),  # we support whatever sentinelhub-py supports
        )

    def process(self, arguments):
        start_time = time.time()
        collection_id = self.validate_parameter(arguments, "id", required=True, allowed_types=[str])
        spatial_extent = self.validate_parameter(arguments, "spatial_extent", required=True)
        temporal_extent = self.validate_parameter(arguments, "temporal_extent", required=True)
        temporal_extent = _clean_temporal_extent(temporal_extent)
        bands = self.validate_parameter(arguments, "bands", default=None, allowed_types=[type(None), list])
        properties = self.validate_parameter(arguments, "properties", required=False, allowed_types=[type(None), dict])

        if bands is not None and not len(bands):
            raise ProcessParameterInvalid("load_collection", "bands", "At least one band must be specified.")

        bbox = load_collectionEOTask._convert_bbox(spatial_extent)

        # check if the bbox is within the allowed limits:
        options = arguments.get("options", {})
        if options.get("width") or options.get("height"):
            width = options.get("width", options.get("height"))
            height = options.get("height", options.get("width"))
        else:
            width, height = sentinelhub.geo_utils.bbox_to_dimensions(bbox, 10.0)

        band_aliases = {}
        band_wavelengths = {}

        if collection_id == "S2L1C":
            dataset = "S2L1C"
            bands = validate_bands(bands, S2_L1C_BANDS, collection_id)
            kwargs = dict(
                data_collection=DataCollection.SENTINEL2_L1C,
                layer=SENTINELHUB_LAYER_ID_S2L1C,
                maxcc=1.0,  # maximum allowed cloud cover of original ESA tiles
            )
            dataFilter_params = {
                "previewMode": "EXTENDED_PREVIEW",
            }
            band_aliases = S2_L1C_ALIASES
            band_wavelengths = S2_L1C_WAVELENGTHS

        elif collection_id == "S2L2A":
            dataset = "S2L2A"
            bands = validate_bands(bands, S2_L2A_BANDS, collection_id)
            kwargs = dict(
                data_collection=DataCollection.SENTINEL2_L2A,
                layer=SENTINELHUB_LAYER_ID_S2L2A,
                maxcc=1.0,  # maximum allowed cloud cover of original ESA tiles
            )
            dataFilter_params = {
                "previewMode": "EXTENDED_PREVIEW",
            }
            band_aliases = S2_L2A_ALIASES
            band_wavelengths = S2_L2A_WAVELENGTHS

        elif collection_id == "S1GRDIW":
            dataset = "S1GRD"
            bands = validate_bands(bands, S1_GRD_IW_BANDS, collection_id)

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
            kwargs = dict(
                data_collection=DataCollection.SENTINEL1_IW,
                layer=SENTINELHUB_LAYER_ID_S1GRD,
            )
            dataFilter_params = {}

        elif collection_id == "BYOC":
            if properties is None or properties.get("byoc_collection_id") is None:
                raise ProcessParameterInvalid(
                    "load_collection", "properties", 'Parameter "byoc_collection_id" not provided in "properties".'
                )

            byoc_collection_id = properties["byoc_collection_id"]
            dataset = "byoc-" + byoc_collection_id
            kwargs = {}
            dataFilter_params = {}

            self.logger.debug(f"Requesting dates between: {temporal_extent}")
            dates = get_collection_times(self, byoc_collection_id, bbox, temporal_extent)
            orbit_dates = [{"from": d, "to": d} for d in dates]

        else:
            raise ProcessParameterInvalid("load_collection", "id", "Unknown collection id.")

        if collection_id != "BYOC":
            self.logger.debug(f"Requesting dates between: {temporal_extent}")

            request = WmsRequest(
                **kwargs,
                instance_id=SENTINELHUB_INSTANCE_ID,
                bbox=bbox,
                time=temporal_extent,
                width=width,
                height=height,
            )
            dates = request.get_dates()
            orbit_dates = get_orbit_dates(dates)

        response_data, orbit_times_middle = download_data(
            self, dataset, orbit_dates, width, height, bbox, temporal_extent, bands, dataFilter_params
        )

        # The last dimension in the returned data is dataMask (https://docs.sentinel-hub.com/api/latest/user-guides/datamask/).
        # xarray provides its own mechanism for masking data, let's use it:
        mask = response_data[:, :, :, -1:]  # ":" keeps the dimension
        mask = np.repeat(mask, len(bands), axis=-1).astype(bool)
        data = response_data[:, :, :, :-1]
        masked_data = da.ma.masked_array(data, mask=~mask)

        # Each band has:
        # - band name
        # - (optional) alias
        # - (optional) wavelength
        # Since some processes (filter_bands, ndvi) depend on this information, we must include it in the datacube.
        bands_dim = [Band(b, band_aliases.get(b), band_wavelengths.get(b)) for b in bands]

        xrdata = xr.DataArray(
            masked_data,
            dims=("t", "y", "x", "band"),
            coords={
                "band": bands_dim,
                "t": orbit_times_middle,
            },
            attrs={
                "bbox": bbox,
            },
        )
        self.logger.debug(f"Returning xarray, job [{self.job_id}] execution time: {time.time() - start_time}")
        return xrdata
