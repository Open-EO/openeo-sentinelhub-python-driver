from sentinelhub import DownloadRequest, SentinelHubDownloadClient


def create_processing_request(
    bbox=None,
    geometry=None,
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
            "bounds": construct_input_bounds(bbox, geometry),
            "data": [
                {
                    "type": collection.api_id,
                    "dataFilter": {
                        "timeRange": {
                            "from": from_date.isoformat() + "Z",
                            "to": to_date.isoformat() + "Z",
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
        url=url,
        post_values=request_raw_dict,
        data_type=mimetype,
        headers={"content-type": "application/json"},
        use_session=True,
    )

    download_request.raise_if_invalid()

    client = SentinelHubDownloadClient(config=config)
    return client.download(download_request)


def construct_input_bounds(bbox, geometry):
    bounds = dict()
    if bbox:
        bounds["bbox"] = bbox
        bounds["properties"] = bbox.crs.opengis_string
    if geometry:
        bounds["geometry"] = geometry
    return bounds
