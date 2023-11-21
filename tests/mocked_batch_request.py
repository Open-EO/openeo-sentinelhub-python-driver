def create_mocked_batch_request(batch_request_id):
    return {
        "id": batch_request_id,
        "userId": "2c4a230c-5085-4924-a3e1-25fb4fc5965b",
        "created": "2019-08-24T14:15:22Z",
        "processRequest": {
            "input": {
                "bounds": {
                    "bbox": [13.822174072265625, 45.85080395917834, 14.55963134765625, 46.29191774991382],
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [14.000701904296873, 46.23685258143992],
                                [13.822174072265625, 46.09037664604301],
                                [14.113311767578125, 45.85080395917834],
                                [14.55963134765625, 46.038922598236],
                                [14.441528320312498, 46.28717293114449],
                                [14.17236328125, 46.29191774991382],
                                [14.000701904296873, 46.23685258143992],
                            ]
                        ],
                    },
                    "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"},
                },
                "data": [
                    {
                        "type": "sentinel-2-l1c",
                        "id": "string",
                        "dataFilter": {
                            "timeRange": {"from": "2018-10-01T00:00:00.000Z", "to": "2018-11-01T00:00:00.000Z"},
                            "mosaickingOrder": "mostRecent",
                            "maxCloudCoverage": 100,
                            "previewMode": "DETAIL",
                        },
                        "processing": {"upsampling": "NEAREST", "downsampling": "NEAREST", "harmonizeValues": True},
                    }
                ],
            },
            "output": {"responses": [{"identifier": "<identifier>", "format": {"type": "image/png"}}]},
            "evalscript": "string",
        },
        "tilingGridId": 0,
        "tilingGrid": {"id": 0, "resolution": 0, "bufferX": None, "bufferY": None},
        "resolution": 0,
        "output": {
            "defaultTilePath": "string",
            "overwrite": False,
            "skipExisting": False,
            "cogOutput": False,
            "cogParameters": {
                "overviewLevels": [0],
                "overviewMinSize": "min(blockxsize, blockysize)",
                "resamplingAlgorithm": "average",
                "blockxsize": 1024,
                "blockysize": 1024,
                "usePredictor": True,
                "noData": 0,
            },
            "createCollection": False,
            "collectionId": None,
            "responses": [{"identifier": "<identifier>", "tilePath": "string"}],
        },
        "bucketName": "string",
        "description": "string",
        "valueEstimate": 0,
        "tileCount": 0,
        "tileWidthPx": 0,
        "tileHeightPx": 0,
        "userAction": "NONE",
        "userActionUpdated": "2019-08-24T14:15:22Z",
        "status": "PROCESSING",
        "error": None,
    }
