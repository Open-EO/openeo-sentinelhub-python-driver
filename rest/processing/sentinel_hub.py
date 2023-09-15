import os
import json

from sentinelhub import SentinelHubBatch
from sentinelhub.exceptions import DownloadFailedException
from openeoerrors import ProcessGraphComplexity
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
            "responses": [
                {"identifier": "default", "format": {"type": mimetype.get_string()}},
                {"identifier": "userdata", "format": {"type": "application/json"}},
            ],
        }
        if width is not None:
            output["width"] = width
        if height is not None:
            output["height"] = height
        return output

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
        mimetype=None,
        resampling_method=None,
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

    def get_utm_tiling_grids(self):
        tiling_grids = []
        for tiling_grid in self.batch.iter_tiling_grids():
            if tiling_grid["properties"]["unit"] == "METRE":
                tiling_grids.append(tiling_grid)
        return tiling_grids
