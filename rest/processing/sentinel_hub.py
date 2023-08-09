import os
import json

from sentinelhub import SentinelHubBatch
from sentinelhub.exceptions import DownloadFailedException
from openeoerrors import ProcessGraphComplexity, Internal
import requests

from buckets import BUCKET_NAMES
from processing.processing_api_request import ProcessingAPIRequest
from processing.const import (
    SampleType,
    TilingGridUnit,
    CustomMimeType,
    sample_type_to_zarr_dtype,
    default_sample_type_for_mimetype,
)


class SentinelHub:
    def __init__(self, user=None, service_base_url=None):
        self.S3_BUCKET_NAME = BUCKET_NAMES.get(service_base_url)
        self.user = user
        self.batch = SentinelHubBatch()

        if self.user is not None:
            self.batch.client.session = self.user.session

        if service_base_url is not None:
            self.batch.service_url = self.batch._get_service_url(service_base_url)

    def create_processing_request(
        self,
        bbox=None,
        geometry=None,
        epsg_code=None,
        collection=None,
        evalscript=None,
        from_date=None,
        to_date=None,
        width=None,
        height=None,
        mimetype=None,
        resampling_method=None,
    ):
        if width > 2500 or height > 2500:
            raise ProcessGraphComplexity("Dimensions exceed limit of 2500X2500")

        request_raw_dict = self.get_request_dictionary(
            bbox=bbox,
            geometry=geometry,
            epsg_code=epsg_code,
            collection=collection,
            evalscript=evalscript,
            from_date=from_date,
            to_date=to_date,
            width=width,
            height=height,
            mimetype=mimetype,
            resampling_method=resampling_method,
        )

        return ProcessingAPIRequest(
            f"{collection.service_url}/api/v1/process", request_raw_dict, user=self.user
        ).fetch()

    def get_request_dictionary(
        self,
        bbox=None,
        geometry=None,
        epsg_code=None,
        collection=None,
        evalscript=None,
        from_date=None,
        to_date=None,
        width=None,
        height=None,
        mimetype=None,
        resampling_method=None,
        preview_mode="EXTENDED_PREVIEW",
    ):
        return {
            "input": {
                "bounds": self.construct_input_bounds(bbox, epsg_code, geometry),
                "data": [
                    {
                        "type": collection.api_id,
                        "dataFilter": {
                            "timeRange": {
                                "from": from_date.isoformat(),
                                "to": to_date.isoformat(),
                            },
                            "previewMode": preview_mode,
                        },
                        "processing": self.construct_data_processing(resampling_method),
                    }
                ],
            },
            "output": self.construct_output(width, height, mimetype),
            "evalscript": evalscript,
        }

    def construct_input_bounds(self, bbox, epsg_code, geometry):
        bounds = dict()
        if bbox:
            bounds["bbox"] = list(bbox)
            bounds["properties"] = {"crs": f"http://www.opengis.net/def/crs/EPSG/0/{epsg_code}"}
        if geometry:
            bounds["geometry"] = geometry
        return bounds

    def construct_data_processing(self, resampling_method):
        processing = dict()
        if resampling_method:
            processing["upsampling"] = resampling_method.value
            processing["downsampling"] = resampling_method.value
        return processing

    def construct_output(self, width, height, mimetype):
        output = {
            "responses": [{"identifier": "default", "format": {"type": mimetype.get_string()}}],
        }
        if width is not None:
            output["width"] = width
        if height is not None:
            output["height"] = height
        return output

    def construct_zarr_output(
        self,
        tiling_grid_resolution=None,
        tiling_grid_tile_width=None,
        sample_type=None,
    ):

        if tiling_grid_resolution == None or tiling_grid_tile_width == None:
            raise Internal("construct_zarr_output: parameter tiling_grid_resolution or tiling_grid_tile_width is None")

        # might not work for CREODIAS
        zarr_path = f"s3://{self.S3_BUCKET_NAME}/<requestId>"

        # Zarr format version. Currently only version 2 is supported.
        # https://docs.sentinel-hub.com/api/latest/reference/#tag/batch_process/operation/createNewBatchProcessingRequest
        zarr_format = 2

        # Data type/encoding. Allowed values depend on the sampleType defined in evalscript:
        # - |u1: 8-bit unsigned integer, recommended for sampleType UINT8 and AUTO,
        # - |i1: 8-bit signed integer, recommended for sampleType INT8,
        # - <u2,>u2: 16-bit unsigned integer (little and big endian, respectively), recommended for sampleType UINT16, allowed for UINT8 and AUTO,
        # - <i2,>i2: 16-bit signed integer (little and big endian, respectively), recommended for sampleType INT16, allowed for UINT8, INT8 and AUTO,
        # - <f4, >f4, <f8, >f8: float (little/big endian single precision, little/big endian double precision, respectively), recommended for sampleType FLOAT32, allowed for any sampleType.
        # Recommended values encode the chosen sampleType losslessly, while other allowed values encode the same values in a wider data type but do not add any more precision.
        default_sample_type = default_sample_type_for_mimetype.get(CustomMimeType.ZARR, SampleType.FLOAT32)
        zarr_sample_type = sample_type if sample_type is not None else default_sample_type
        zarr_dtype = sample_type_to_zarr_dtype.get(zarr_sample_type)

        # Layout of values within each chunk of the array. Currently only "C" is supported, which means row-major order.
        # https://docs.sentinel-hub.com/api/latest/reference/#tag/batch_process/operation/createNewBatchProcessingRequest
        zarr_order = "C"

        # A list of integers defining the length of each dimension of a chunk of the array, e.g. [1, 1000, 1000].
        # The first element (time dimension chunking) must be 1.
        # The second and third (latidude/y and longitude/x-dimension chunking, respectively) must evenly divide the batch output tile raster size. For example, when using the LAEA 100km grid with an output resolution of 50 m, each batch tile will be 2000 x 2000 pixels, thus valid chunking sizes are 2000, 1000, 500, 400 etc.
        # https://docs.sentinel-hub.com/api/latest/reference/#tag/batch_process/operation/createNewBatchProcessingRequest
        zarr_spatial_dimension_chunking = tiling_grid_tile_width / tiling_grid_resolution
        zarr_chunks = [1, zarr_spatial_dimension_chunking, zarr_spatial_dimension_chunking]

        # A scalar value providing the default value for portions of the array corresponding to non-existing chunks:
        # - any chunks consisting solely of this value will not be written,
        # - the value will be included in the output Zarr metadata.
        # Note: fill_value must be representable by the array's dtype.
        # Note: any grid tiles that are within Zarr envelope but outside of processRequest.input.bounds.geometry will not be processed by batch at all. No chunks will thus be written for those tiles, thus fill_value is required to ensure a valid Zarr is created.
        # https://docs.sentinel-hub.com/api/latest/reference/#tag/batch_process/operation/createNewBatchProcessingRequest
        zarr_fill_value = 0

        zarr_output = {
            "path": zarr_path,
            "group": {"zarr_format": zarr_format},
            "arrayParameters": {
                "dtype": zarr_dtype,
                "order": zarr_order,
                "chunks": zarr_chunks,
                "fill_value": zarr_fill_value,
            },
        }

        return zarr_output

    def create_batch_job(
        self,
        bbox=None,
        geometry=None,
        epsg_code=None,
        collection=None,
        evalscript=None,
        from_date=None,
        to_date=None,
        tiling_grid_id=None,
        tiling_grid_resolution=None,
        tiling_grid_tile_width=None,
        mimetype=None,
        resampling_method=None,
        sample_type=None,
    ):
        request_raw_dict = self.get_request_dictionary(
            bbox=bbox,
            geometry=geometry,
            epsg_code=epsg_code,
            collection=collection,
            evalscript=evalscript,
            from_date=from_date,
            to_date=to_date,
            mimetype=mimetype,
            resampling_method=resampling_method,
            preview_mode="DETAIL",
        )

        batch_request = self.batch.create(
            request_raw_dict,
            tiling_grid=SentinelHubBatch.tiling_grid(
                grid_id=tiling_grid_id, resolution=tiling_grid_resolution, buffer=(0, 0)
            ),
            bucket_name=self.S3_BUCKET_NAME if mimetype != CustomMimeType.ZARR else None,
            zarrOutput=self.construct_zarr_output(tiling_grid_resolution, tiling_grid_tile_width, sample_type)
            if mimetype == CustomMimeType.ZARR
            else None,
        )
        return batch_request.request_id

    def start_batch_job(self, batch_request_id):
        batch_request = self.get_batch_request_info(batch_request_id)
        self.batch.start_job(batch_request)

    def restart_batch_job(self, batch_request_id):
        batch_request = self.get_batch_request_info(batch_request_id)
        self.batch.restart_job(batch_request)

    def cancel_batch_job(self, batch_request_id):
        batch_request = self.get_batch_request_info(batch_request_id)
        self.batch.cancel_job(batch_request)

    def delete_batch_job(self, batch_request_id):
        batch_request = self.get_batch_request_info(batch_request_id)
        self.batch.delete_request(batch_request)

    def get_batch_request_info(self, batch_request_id):
        try:
            return self.batch.get_request(batch_request_id)
        except DownloadFailedException as e:
            return None

    def start_batch_job_analysis(self, batch_request_id):
        batch_request = self.batch.get_request(batch_request_id)
        self.batch.start_analysis(batch_request)

    def get_utm_tiling_grids_SH_PY(self):
        tiling_grids = []
        for tiling_grid in self.batch.iter_tiling_grids():
            if tiling_grid["properties"]["unit"] == "METRE":
                tiling_grids.append(tiling_grid)
        return tiling_grids

    def get_tiling_grids(self, unit: TilingGridUnit, only_single_crs: bool):
        access_token = self.batch.client.session.token["access_token"]
        tiling_grids = []
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}
        resp = requests.get("https://services.sentinel-hub.com/api/v1/batch/tilinggrids", headers=headers)
        json = resp.json()
        iter_grids = iter(json.get("data"))
        for tiling_grid in iter_grids:
            if tiling_grid["properties"]["unit"] == unit.value:
                if only_single_crs is False or (
                    only_single_crs is True and tiling_grid["properties"]["singleCrs"] is True
                ):
                    tiling_grids.append(tiling_grid)
        return tiling_grids
