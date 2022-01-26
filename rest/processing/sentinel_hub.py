import os
from sentinelhub import DownloadRequest, SentinelHubDownloadClient, SHConfig


def create_processing_request(
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
    request_raw_dict = {
        "input": {
            "bounds": construct_input_bounds(bbox, epsg_code, geometry),
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
        "output": {
            "width": width,
            "height": height,
            "responses": [{"identifier": "default", "format": {"type": mimetype.get_string()}}],
        },
        "evalscript": evalscript,
    }

    download_request = DownloadRequest(
        request_type="POST",
        url="https://services.sentinel-hub.com/api/v1/process",
        post_values=request_raw_dict,
        data_type=mimetype,
        headers={"content-type": "application/json"},
        use_session=True,
    )

    download_request.raise_if_invalid()

    config = SHConfig()
    CLIENT_ID = os.environ.get("CLIENT_ID")
    CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
    config.sh_client_id = CLIENT_ID
    config.sh_client_secret = CLIENT_SECRET

    client = SentinelHubDownloadClient(config=config)
    return client.download(download_request, decode_data=False)


def construct_input_bounds(bbox, epsg_code, geometry):
    bounds = dict()
    if bbox:
        bounds["bbox"] = list(bbox)
        bounds["properties"] = {"crs": f"http://www.opengis.net/def/crs/EPSG/0/{epsg_code}"}
    if geometry:
        bounds["geometry"] = geometry
    return bounds
