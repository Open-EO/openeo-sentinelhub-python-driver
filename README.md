## Running locally


### Prerequisites
Mandatory: 
- `.env` files in root directory and in `./rest` directory
  - In both root directory of this project and in `./rest` directory, copy the respective `.env.example` to `.env` and enter the variables in `.env` file.
- `docker-compose`
  - Check [README-docker.md](README-docker.md) for help about installing Docker and `docker-compose`.
- Python 3.6
  - Check [README-python.md](README-python.md) for help about installing Python 3.6 and managing multiple Python versions.

### Running services and REST API

First, start up all services:
```
$ docker-compose up -d
```

Download definitions of defined processes:
```
$ ./download-process-definitions.sh
```

Then, python libraries need to be installed:
```
$ cd rest/
$ pipenv install
```

Tables on DynamoDB need to be created manually:
```
$ pipenv shell
<pipenv> $ python dynamodb.py
```

Then the REST API server can be run:
```
<pipenv> $ python app.py
```

### Troubleshooting

If validator complains about process graphs that are clearly correct (and which are valid on production deployment), there are two things than can be done:

1) Remove and reinstall python environment:

    ```
    $ cd rest/
    $ pipenv --rm
    $ pipenv install
    ```

2) Remove and re-download process definitions:

    ```
    $ rm rest/process_definitions/*
    $ ./download-process-definitions.sh
    ```

# Examples

## REST

### Get auth token

Authenticate using your Sentinel Hub clientId and clientSecret:
```
$ curl -u '<SH-client-id>:<SH-client-secret>' http://127.0.0.1:5000/credentials/basic
```

Save the token to an env var for later examples:
```
$ export AUTH_TOKEN='...'
```

### Process and download data synchronously

Trigger processing:

```
POST /results HTTP/1.1
Content-Type: application/json

{
  "process": {
    "process_graph": {
      "loadco1": {
        "process_id": "load_collection",
        "arguments": {
          "id": "S2L1C",
          "temporal_extent": [
              "2019-08-16",
              "2019-08-18"
          ],
          "spatial_extent": {
              "west": 12.32271,
              "east": 12.33572,
              "north": 42.07112,
              "south": 42.06347
          }
        }
      },
      "ndvi1": {
          "process_id": "ndvi",
          "arguments": {
            "data": {
                "from_node": "loadco1"
            }
          }
      },
      "result1": {
          "process_id": "save_result",
          "arguments": {
            "data": {
                "from_node": "ndvi1"
            },
            "format": "gtiff"
          },
          "result": true
      }
    }
  }
}
```

Using curl:
```bash
$ curl -i -X POST -H "Authorization: Bearer basic//$AUTH_TOKEN" -H "Content-Type: application/json" -d '{ "process": { "process_graph": { "loadco1": { "process_id": "load_collection", "arguments": { "id": "S2L1C", "temporal_extent": [ "2019-08-16", "2019-08-18" ], "spatial_extent": { "west": 12.32271, "east": 12.33572, "north": 42.07112, "south": 42.06347 } } }, "ndvi1": { "process_id": "ndvi", "arguments": { "data": { "from_node": "loadco1" } } }, "result1": { "process_id": "save_result", "arguments": { "data": { "from_node": "ndvi1" }, "format": "gtiff" }, "result": true} } } }' http://localhost:5000/result/
```


### Jobs

List all jobs:
```
$ curl http://localhost:5000/jobs/
```

Create a job:
```
POST /jobs HTTP/1.1
Content-Type: application/json

{
  "process": {
    "process_graph": {
      "loadco1": {
        "process_id": "load_collection",
        "arguments": {
          "id": "S2L1C",
          "spatial_extent": {
            "west": 12.32271,
            "east": 12.33572,
            "north": 42.07112,
            "south": 42.06347
          },
          "temporal_extent": ["2019-08-16", "2019-08-18"]
        }
      },
      "ndvi1": {
        "process_id": "ndvi",
        "arguments": {
          "data": {"from_node": "loadco1"}
        }
      },
      "result1": {
        "process_id": "save_result",
        "arguments": {
          "data": {"from_node": "ndvi1"},
          "format": "gtiff"
        },
        "result": true
      }
    }
  }
}
```

Using curl:
```bash
$ curl -i -X POST -H "Content-Type: application/json" -d '{"process": {"process_graph": {"loadco1": {"process_id": "load_collection", "arguments": {"id": "S2L1C", "temporal_extent": ["2019-08-16", "2019-08-18"], "spatial_extent": {"west": 12.32271, "east": 12.33572, "north": 42.07112, "south": 42.06347}}}, "ndvi1": {"process_id": "ndvi", "arguments": {"data": {"from_node": "loadco1"}}}, "result1": {"process_id": "save_result", "arguments": {"data": {"from_node": "ndvi1"}, "format": "gtiff"}, "result": true}}}}' http://localhost:5000/jobs/
```

Listing all jobs should now include the new job: (note that id will be different)
```
$ curl http://localhost:5000/jobs/
{
  "jobs": [
    {
      "description": null,
      "id": "6520894b-d41d-40d1-bcff-67eafab4eced",
      "title": null
    }
  ],
  "links": [
    {
      "href": "/jobs/6520894b-d41d-40d1-bcff-67eafab4eced",
      "title": null
    }
  ]
}
```

Taking the job id, we can check job details:
```
$ curl http://localhost:5000/jobs/6520894b-d41d-40d1-bcff-67eafab4eced
{
  "description": null,
  "error": [
    null
  ],
  "id": "6520894b-d41d-40d1-bcff-67eafab4eced",
  "process_graph": {
    "loadco1": {
      "arguments": {
        "id": "S2L1C",
        "spatial_extent": {
          "east": 12.33572,
          "north": 42.07112,
          "south": 42.06347,
          "west": 12.32271
        },
        "temporal_extent": ["2019-08-16", "2019-08-18"]
      },
      "process_id": "load_collection"
    },
    "ndvi1": {
      "arguments": {
        "data": {
          "from_node": "loadco1"
        }
      },
      "process_id": "ndvi"
    },
    "result1": {
      "arguments": {
        "data": {
          "from_node": "ndvi1"
        },
        "format": "gtiff"
      },
      "process_id": "save_result",
      "result": true
    }
  },
  "status": "created",
  "created": [
    "2019-08-30T09:18:12.250595+00:00"
  ],
  "title": null
}
```

And start it by using the returned `id`:
```
$ curl -X POST -H "Authorization: Bearer basic//$AUTH_TOKEN" http://localhost:5000/jobs/6520894b-d41d-40d1-bcff-67eafab4eced/results
```

### Services

Get supported service types:
```
$ curl http://localhost:5000/service_types
```

Currently, only `XYZ` service type is supported. We create the service:
```
$ curl -i 'http://localhost:5000/services' -H 'Content-Type: application/json;charset=utf-8' -d '{"title":null,"description":null,"process": {"process_graph":{"loadco1": {"process_id": "load_collection", "arguments": {"id": "S2L1C", "temporal_extent": ["2019-08-16", "2019-08-18"], "spatial_extent": {"west":{"variable_id":"spatial_extent_west"},"east":{"variable_id":"spatial_extent_east"},"north":{"variable_id":"spatial_extent_north"},"south":{"variable_id":"spatial_extent_south"}}}}, "ndvi1": {"process_id": "ndvi", "arguments": {"data": {"from_node": "loadco1"}}}, "result1": {"process_id": "save_result", "arguments": {"data": {"from_node": "ndvi1"}, "format": "gtiff"}, "result": true}}},"type":"XYZ","enabled":true,"plan":null,"budget":null}'
...
Location: http://localhost:5000/services/df9cf197-9125-4db6-a684-e9e02678cb4b
OpenEO-Identifier: df9cf197-9125-4db6-a684-e9e02678cb4b
...
```

As with jobs, IDs will be different. Then we can issue requests using the returned service `id`:
```
$ curl -H "Authorization: Bearer basic//$AUTH_TOKEN" http://localhost:5000/service/xyz/df9cf197-9125-4db6-a684-e9e02678cb4b/15/17194/11145 > /tmp/test.jpeg
```


## AWS

Since we are running everything locally, make sure that the default entry in `~/.aws/credentials` has correct credentials:
```
[default]
aws_access_key_id=AKIAIOSFODNN7EXAMPLE
aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

While executing the examples, we can check the data of the jobs in DynamoDB by using AWS CLI tool:
```
$ aws dynamodb --endpoint http://localhost:8000 scan --table-name shopeneo_jobs
```

Similarly, S3 can be inspected:
```
$ aws s3 --endpoint http://localhost:9000 ls
2019-08-30 12:44:38 com.sinergise.openeo.results
$ aws s3 --endpoint http://localhost:9000 ls s3://com.sinergise.openeo.results
                    PRE 41a32a56-29bd-42d7-9c27-5af98a3421a8/
$ aws s3 --endpoint http://localhost:9000 ls s3://com.sinergise.openeo.results/41a32a56-29bd-42d7-9c27-5af98a3421a8/
2019-08-30 12:44:38      73206 result-0.tiff
```

And results downloaded to local filesystem if needed:
```
$ mkdir /tmp/results
$ aws s3 --endpoint http://localhost:9000 sync s3://com.sinergise.openeo.results/41a32a56-29bd-42d7-9c27-5af98a3421a8/ /tmp/results
download: s3://com.sinergise.openeo.results/41a32a56-29bd-42d7-9c27-5af98a3421a8/result-0.tiff to /tmp/asdf/result-0.tiff
$ gdalinfo /tmp/results/result-0.tiff
Driver: GTiff/GeoTIFF
...
```