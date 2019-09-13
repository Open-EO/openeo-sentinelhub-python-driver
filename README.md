## Running locally

First, start up all services:
```
$ docker-compose up -d
```

Download definitions of defined processes:
```
$ chmod +x download-process-definitions.sh
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

# Examples

## REST

List all jobs:
```
$ curl http://localhost:5000/jobs/
```

Create a job:
```
POST /jobs HTTP/1.1
Content-Type: application/json

{
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
        "temporal_extent": "2019-08-17"
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
```

Using curl:
```bash
$ curl -i -X POST -H "Content-Type: application/json" -d '{"process_graph": {"loadco1": {"process_id": "load_collection", "arguments": {"id": "S2L1C", "temporal_extent": "2019-08-17", "spatial_extent": {"west": 12.32271, "east": 12.33572, "north": 42.07112, "south": 42.06347}}}, "ndvi1": {"process_id": "ndvi", "arguments": {"data": {"from_node": "loadco1"}}}, "result1": {"process_id": "save_result", "arguments": {"data": {"from_node": "ndvi1"}, "format": "gtiff"}, "result": true}}}' http://localhost:5000/jobs/
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
        "temporal_extent": "2019-08-17"
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
  "status": "submitted",
  "submitted": [
    "2019-08-30T09:18:12.250595+00:00"
  ],
  "title": null
}
```

And start it:
```
$ curl -X POST http://localhost:5000/jobs/6520894b-d41d-40d1-bcff-67eafab4eced/results
```

## AWS

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