import os
from sentinelhub import DownloadRequest, SentinelHubDownloadClient, SHConfig, SentinelHubBatch
from openeoerrors import ProcessGraphComplexity


class SentinelHub:
    def __init__(self):
        self.config = SHConfig()
        CLIENT_ID = os.environ.get("TESTS_SH_CLIENT_ID")
        CLIENT_SECRET = os.environ.get("TESTS_SH_CLIENT_SECRET")
        self.config.sh_client_id = CLIENT_ID
        self.config.sh_client_secret = CLIENT_SECRET
        self.S3_BUCKET_NAME = os.environ.get("RESULTS_S3_BUCKET_NAME", "com.sinergise.openeo.results")
        self.batch = SentinelHubBatch(config=self.config)

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
        download_request = DownloadRequest(
            request_type="POST",
            url=f"{collection.service_url}/api/v1/process",
            post_values=request_raw_dict,
            data_type=mimetype,
            headers={"content-type": "application/json"},
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

    def get_appropriate_tiling_grid_id(self, batch):
        return 0

    def create_batch_job(
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
        request_raw_dict = self.get_request_dictionary(
            bbox=bbox,
            geometry=geometry,
            epsg_code=epsg_code,
            collection=collection,
            evalscript=evalscript,
            from_date=from_date,
            to_date=to_date,
            mimetype=mimetype,
        )

        batch_request = self.batch.create(
            request_raw_dict,
            tiling_grid=SentinelHubBatch.tiling_grid(
                grid_id=self.get_appropriate_tiling_grid_id(self.batch), resolution=10, buffer=(0, 0)
            ),
            bucket_name=self.S3_BUCKET_NAME,
        )
        return batch_request.request_id

    def start_batch_job(self, batch_request_id):
        batch_request = self.batch.get_request(batch_request_id)
        self.batch.start_job(batch_request)

    def cancel_batch_job(self, batch_request_id):
        batch_request = self.batch.get_request(batch_request_id)
        self.batch.cancel_job(batch_request)

    def delete_batch_job(self, batch_request_id):
        batch_request = self.batch.get_request(batch_request_id)
        self.batch.delete_request(batch_request)

    def get_batch_request_info(self, batch_request_id):
        return self.batch.get_request(batch_request_id)
