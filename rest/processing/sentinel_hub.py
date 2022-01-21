from sentinelhub import DownloadRequest, SentinelHubDownloadClient, MimeType, CRS


def create_processing_request(collection=None, evalscript=None, bbox=None, geometry=None):
    request_raw_dict = {
        "input": {
            "bounds": {
                "properties": {"crs": bbox.crs.opengis_string},
                "bbox": list(bbox),
            },
            "data": [
                {
                    "type": data_collection.api_id,
                    "dataFilter": {
                        "timeRange": {
                            "from": from_date.isoformat() + "Z",
                            "to": to_date.isoformat() + "Z",
                        },
                        "mosaickingOrder": "mostRecent",
                        # "orbitDirection": "DESCENDING",
                        "previewMode": "EXTENDED_PREVIEW",
                        "maxCloudCoverage": 100,
                    },
                    "processing": {"view": "NADIR", **processing_options},
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
