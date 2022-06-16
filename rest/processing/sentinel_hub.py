import os

from sentinelhub import DownloadRequest, SentinelHubDownloadClient, SentinelHubBatch, SentinelHubSession
from sentinelhub.exceptions import DownloadFailedException
from openeoerrors import ProcessGraphComplexity

from processing.const import sh_config


class SentinelHub:
    def __init__(self, access_token=None, service_base_url=None):
        self.config = sh_config
        self.S3_BUCKET_NAME = os.environ.get("RESULTS_S3_BUCKET_NAME", "com.sinergise.openeo.results")
        self.batch = SentinelHubBatch(config=self.config)
        self.access_token = access_token

        if access_token is not None:
            # This is an ugly hack to set custom access token
            self.batch.client.session = SentinelHubSession(config=self.config)
            self.batch.client.session._token = {"access_token": access_token, "expires_at": 99999999999999}

        if service_base_url is not None:
            self.config.sh_base_url = service_base_url
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
        )

        headers = {"content-type": "application/json"}
        if self.access_token is not None:
            headers["Authorization"] = f"Bearer {self.access_token}"

        download_request = DownloadRequest(
            request_type="POST",
            url=f"{collection.service_url}/api/v1/process",
            post_values=request_raw_dict,
            data_type=mimetype,
            headers=headers,
            use_session=True,
        )

        download_request.raise_if_invalid()

        client = SentinelHubDownloadClient(config=self.config)
        return client.download(download_request, decode_data=False)

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

    def construct_output(self, width, height, mimetype):
        output = {
            "responses": [{"identifier": "default", "format": {"type": mimetype.get_string()}}],
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
            preview_mode="DETAIL",
        )

        batch_request = self.batch.create(
            request_raw_dict,
            tiling_grid=SentinelHubBatch.tiling_grid(
                grid_id=tiling_grid_id, resolution=tiling_grid_resolution, buffer=(0, 0)
            ),
            bucket_name=self.S3_BUCKET_NAME,
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
