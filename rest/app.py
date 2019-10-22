import os
import datetime
from logging import log, INFO, WARN
import json
import glob
import time
import requests
import boto3
import flask
from flask import Flask, url_for, jsonify
from flask_marshmallow import Marshmallow
from flask_cors import CORS
from sentinelhub import BBox

import globalmaptiles
from schemas import (
    PostProcessGraphsSchema,
    PatchProcessGraphsSchema,
    PGValidationSchema,
    PostResultSchema,
    PostJobsSchema,
    PatchJobsSchema,
    PostServicesSchema,
    PatchServicesSchema,
)
from dynamodb import JobsPersistence, ProcessGraphsPersistence, ServicesPersistence


app = Flask(__name__)
app.url_map.strict_slashes = False

cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'


RESULTS_S3_BUCKET_NAME = os.environ.get('RESULTS_S3_BUCKET_NAME', 'com.sinergise.openeo.results')
REQUEST_TIMEOUT = 30 # In seconds

FAKE_AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
FAKE_AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', FAKE_AWS_ACCESS_KEY_ID)
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', FAKE_AWS_SECRET_ACCESS_KEY)
S3_LOCAL_URL = os.environ.get('DATA_AWS_S3_ENDPOINT_URL')

@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Accept, Content-Type'  # missing websockets-specific headers
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, PUT, PATCH, OPTIONS'
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Access-Control-Expose-Headers
    response.headers['Access-Control-Expose-Headers'] = 'OpenEO-Costs, Location, OpenEO-Identifier'
    response.headers['Access-Control-Max-Age'] = '3600'  # https://damon.ghost.io/killing-cors-preflight-requests-on-a-react-spa/
    return response


@app.route('/', methods=["GET"])
def api_root():
    return {
        "api_version": "0.4.2",
        "backend_version": os.environ.get('BACKEND_VERSION', "0.0.0").lstrip('v'),
        "title": "Sentinel Hub OpenEO",
        "description": "Sentinel Hub OpenEO by [Sinergise](https://sinergise.com)",
        "endpoints": get_endpoints(),
    }


def get_endpoints():
    """
        Returns a list of endpoints (url and allowed methods).
    """
    endpoints = []
    omitted_urls = ["/static/<path:filename>"]

    for rule in app.url_map.iter_rules():
        url = rule.rule

        if url in omitted_urls:
            continue

        # OpenEO Web Client assumes that the URLs returned will be in the same form as specified in the
        # docs. To accomodate it we simply substitute arrows (around parameters) for curly braces:
        url = url.translate(str.maketrans({
          "<": "{",
          ">": "}",
        }))

        endpoints.append({
            "path": url,
            "methods": list(rule.methods - set(["OPTIONS", "HEAD"])),
        })
    return endpoints


@app.route('/output_formats', methods=["GET"])
def api_output_formats():
    files = glob.iglob("output_formats/*.json")
    output_formats = {}

    for file in files:
        with open(file) as f:
            output_format = os.path.splitext(os.path.basename(file))[0]
            output_formats[output_format] = json.load(f)

    return flask.make_response(jsonify(output_formats), 200)


@app.route('/service_types', methods=["GET"])
def api_service_types():
    files = glob.iglob("service_types/*.json")
    result = {}
    for file in files:
        with open(file) as f:
            key = os.path.splitext(os.path.basename(file))[0]
            result[key] = json.load(f)

    return flask.make_response(jsonify(result), 200)


@app.route('/process_graphs', methods=["GET", "POST"])
@app.route('/process_graphs/<process_graph_id>', methods=["GET", "DELETE", "PATCH"])
def api_process_graphs(process_graph_id=None):
    if flask.request.method in ['GET', 'HEAD']:
        if process_graph_id is None:
            process_graphs = []
            links = []
            for record in ProcessGraphsPersistence.items():
                process_graphs.append({
                    "id": record["id"],
                    "title": record.get("title", None),
                    "description": record.get("description", None),
                })
                links.append({
                    "href": "{}/process_graphs/{}".format(flask.request.url_root, record["id"]),
                    "title": record.get("title", None),
                })
            return {
                "process_graphs": process_graphs,
                "links": links,
            }, 200
        else:
            process_graph = ProcessGraphsPersistence.get_by_id(process_graph_id)
            process_graph["id"] = process_graph_id
            return process_graph, 200

    elif flask.request.method == 'POST':
        data = flask.request.get_json()

        process_graph_schema = PostProcessGraphsSchema()
        errors = process_graph_schema.validate(data)

        if errors:
            # Response procedure for validation will depend on how openeo_pg_parser_python will work
            return flask.make_response(jsonify(
                id = process_graph_id,
                code = 400,
                message = errors,
                links = []
                ), 400)

        record_id = ProcessGraphsPersistence.create(data)

        # add requested headers to 201 response:
        response = flask.make_response('', 201)
        response.headers['Location'] = '/process_graphs/{}'.format(record_id)
        response.headers['OpenEO-Identifier'] = record_id
        return response

    elif flask.request.method == 'DELETE':
        ProcessGraphsPersistence.delete(process_graph_id)
        return flask.make_response('The process graph has been successfully deleted.', 204)

    elif flask.request.method == 'PATCH':
        data = flask.request.get_json()

        process_graph_schema = PatchProcessGraphsSchema()
        errors = process_graph_schema.validate(data)

        if errors:
            # Response procedure for validation will depend on how openeo_pg_parser_python will work
            return flask.make_response(jsonify(
                id = process_graph_id,
                code = 400,
                message = errors,
                links = []
                ), 400)

        for key in data:
            ProcessGraphsPersistence.update_key(process_graph_id, key, data[key])

        return flask.make_response('The process graph data has been updated successfully.', 204)


@app.route('/result', methods=['POST'])
def api_result():
    if flask.request.method == 'POST':
        data = flask.request.get_json()

        schema = PostResultSchema()
        errors = schema.validate(data)

        if errors:
            log(WARN, "Invalid request: {}".format(errors))
            return flask.make_response(jsonify(
                id = None,
                code = 400,
                message = errors,
                links = []
                ), 400)

        data["current_status"] = "queued"
        data["should_be_cancelled"] = False

        return _execute_and_wait_for_job(data)


@app.route('/jobs', methods=['GET','POST'])
def api_jobs():
    if flask.request.method == 'GET':
        jobs = []
        links = []

        for record in JobsPersistence.items():
            jobs.append({
                "id": record["id"],
                "title": record.get("title", None),
                "description": record.get("description", None),
            })
            links.append({
                "href": "{}/jobs/{}".format(flask.request.url_root, record.get("id")),
                "title": record.get("title", None),
            })
        return {
            "jobs": jobs,
            "links": links,
        }, 200

    elif flask.request.method == 'POST':
        data = flask.request.get_json()

        process_graph_schema = PostJobsSchema()
        errors = process_graph_schema.validate(data)

        if errors:
            # Response procedure for validation will depend on how openeo_pg_parser_python will work
            return flask.make_response('Invalid request: {}'.format(errors), 400)

        data["current_status"] = "submitted"
        data["should_be_cancelled"] = False

        record_id = JobsPersistence.create(data)

        # add requested headers to 201 response:
        response = flask.make_response('', 201)
        response.headers['Location'] = '/jobs/{}'.format(record_id)
        response.headers['OpenEO-Identifier'] = record_id
        return response


@app.route('/jobs/<job_id>', methods=['GET','PATCH','DELETE'])
def api_batch_job(job_id):
    job = JobsPersistence.get_by_id(job_id)
    if job is None:
        return flask.make_response(jsonify(
            id = job_id,
            code = "JobNotFound",
            message = "The job does not exist.",
            links = []
            ), 404)

    if flask.request.method == 'GET':
        status = job["current_status"]
        return flask.make_response(jsonify(
            id = job_id,
            title = job.get("title", None),
            description = job.get("description", None),
            process_graph = json.loads(job["process_graph"]),
            status = status,  # "status" is reserved word in DynamoDB
            error = job["error_msg"] if status == "error" else None,
            submitted = job["submitted"],
            updated = job["last_updated"],
            ), 200)

    elif flask.request.method == 'PATCH':
        if job["current_status"] in ["queued","running"]:
            return flask.make_response(jsonify(
                id = job_id,
                code = "JobLocked",
                message = 'Job is locked due to a queued or running batch computation.',
                links = []
                ), 400)

        data = flask.request.get_json()

        process_graph_schema = PatchJobsSchema()
        errors = process_graph_schema.validate(data)

        if errors:
            # Response procedure for validation will depend on how openeo_pg_parser_python will work
            return flask.make_response(jsonify(
                id = job_id,
                code = 400,
                message = errors,
                links = []
                ), 400)


        for key in data:
            JobsPersistence.update_key(job_id, key, data[key])

        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        JobsPersistence.update_key(job_id, "last_updated", timestamp)
        JobsPersistence.update_key(job_id, "current_status", "submitted")

        return flask.make_response('Changes to the job applied successfully.', 204)

    elif flask.request.method == 'DELETE':
        JobsPersistence.delete(job_id)
        return flask.make_response('The job has been successfully deleted.', 204)


@app.route('/jobs/<job_id>/results', methods=['POST','GET','DELETE'])
def add_job_to_queue(job_id):
    if flask.request.method == "POST":
        job = JobsPersistence.get_by_id(job_id)

        if job["current_status"] in ["submitted","finished","canceled","error"]:
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            JobsPersistence.update_key(job_id, "last_updated", timestamp)
            JobsPersistence.update_key(job_id, "current_status", "queued")

            return flask.make_response('The creation of the resource has been queued successfully.', 202)
        else:
            return flask.make_response(jsonify(
                id = job_id,
                code = "JobLocked",
                message = 'Job is locked due to a queued or running batch computation.',
                links = []
                ), 400)

    elif flask.request.method == "GET":
        job = JobsPersistence.get_by_id(job_id)

        if job["current_status"] not in ["finished","error"]:
            return flask.make_response(jsonify(
                id = job_id,
                code = 'JobNotFinished',
                message = 'Job has not finished computing the results yet. Please try again later.',
                links = []
                ), 400)

        if job["current_status"] == "error":
            return flask.make_response(jsonify(
                id = job_id,
                code = job["error_code"],
                message = job["error_msg"],
                links = []
                ), 424)

        s3 = boto3.client('s3',
            endpoint_url=S3_LOCAL_URL,
            region_name="eu-central-1",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )
        links = []
        results = json.loads(job["results"])
        for result in results:
            # create signed url:
            filename = result["filename"]
            object_key = '{}/{}'.format(job_id, os.path.basename(filename))
            url = s3.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': RESULTS_S3_BUCKET_NAME,
                    'Key': object_key,
                }
            )
            mime_type = result["type"]
            links.append({
                'href': url,
                'type': mime_type,
            })

        return flask.make_response(jsonify(
                id = job_id,
                title = job.get("title", None),
                description = job.get("description", None),
                updated = job["last_updated"],  # "updated" is a reserved word in DynamoDB
                links = links,
            ), 200)

    elif flask.request.method == "DELETE":
        job = JobsPersistence.get_by_id(job_id)

        if job["current_status"] in ["queued","running"]:
            JobsPersistence.update_key(job_id, "should_be_cancelled", True)
            return flask.make_response('Processing the job has been successfully canceled.', 200)

        return flask.make_response(jsonify(
            id = job_id,
            code = "JobNotStarted",
            message = "Job hasn't been started yet.",
            links = []
            ), 400)


@app.route('/services', methods=['GET','POST'])
def api_services():
    if flask.request.method == 'GET':
        services = []
        links = []

        for record in ServicesPersistence.items():
            services.append({
                "id": record["id"],
                "title": record.get("title", None),
                "description": record.get("description", None),
                "url": "{}service/{}/{}".format(flask.request.url_root, record["service_type"], record["id"]),
                "type": record["service_type"],
                "enabled": record.get("enabled", True),
                "plan": record.get("plan", None),
                "costs": None,  # this field is not nullable as per API!!!
                "budget": record.get("budget", None),
            })
            links.append({
                "href": "{}services/{}".format(flask.request.url_root, record.get("id")),
                "title": record.get("title", None),
            })
        return {
            "services": services,
            "links": links,
        }, 200

    elif flask.request.method == 'POST':
        data = flask.request.get_json()

        process_graph_schema = PostServicesSchema()
        errors = process_graph_schema.validate(data)
        if errors:
            return flask.make_response('Invalid request: {}'.format(errors), 400)

        record_id = ServicesPersistence.create(data)

        # add requested headers to 201 response:
        response = flask.make_response('', 201)
        response.headers['Location'] = '{}services/{}'.format(flask.request.url_root, record_id)
        response.headers['OpenEO-Identifier'] = record_id
        return response


@app.route('/services/<service_id>', methods=['GET','PATCH','DELETE'])
def api_service(service_id):
    record = ServicesPersistence.get_by_id(service_id)
    if record is None:
        return flask.make_response(jsonify(
            id = service_id,
            code = "ServiceNotFound",
            message = "The service does not exist.",
            links = []
            ), 404)

    if flask.request.method == 'GET':
        return flask.make_response(jsonify({
            "id": record["id"],
            "title": record.get("title", None),
            "description": record.get("description", None),
            "process_graph": json.loads(record["process_graph"]),
            "url": "{}service/{}/{}".format(flask.request.url_root, record["service_type"], record["id"]),
            "type": record["service_type"],
            "enabled": record.get("enabled", True),
            "parameters": {},
            "attributes": {},
            "submitted": record["submitted"],
            "plan": record.get("plan", None),
            "costs": None,  # this field is not nullable as per API!!!
            "budget": record.get("budget", None),
        }), 200)

    elif flask.request.method == 'PATCH':
        data = flask.request.get_json()
        process_graph_schema = PatchServicesSchema()

        errors = process_graph_schema.validate(data)
        if errors:
            # Response procedure for validation will depend on how openeo_pg_parser_python will work
            return flask.make_response(jsonify(
                id = service_id,
                code = 400,
                message = errors,
                links = []
                ), 400)

        for key in data:
            ServicesPersistence.update_key(service_id, key, data[key])

        return flask.make_response('Changes to the service applied successfully.', 204)

    elif flask.request.method == 'DELETE':
        ServicesPersistence.delete(service_id)
        return flask.make_response('The service has been successfully deleted.', 204)


@app.route('/service/xyz/<service_id>/<int:zoom>/<int:tx>/<int:ty>', methods=['GET'])
def api_execute_service(service_id, zoom, tx, ty):
    record = ServicesPersistence.get_by_id(service_id)
    if record is None or record["service_type"].lower() != 'xyz':
        return flask.make_response(jsonify(
            id = service_id,
            code = "ServiceNotFound",
            message = "The service does not exist.",
            links = []
            ), 404)

    # https://www.maptiler.com/google-maps-coordinates-tile-bounds-projection/
    TILE_SIZE = 256
    minLat, minLon, maxLat, maxLon = globalmaptiles.GlobalMercator(tileSize=TILE_SIZE).TileLatLonBounds(tx, ty, zoom)
    variables = {
        "spatial_extent_west": minLon,
        "spatial_extent_south": minLat,
        "spatial_extent_east": maxLon,
        "spatial_extent_north": maxLat,
        "spatial_extent_crs": 4326,
        "tile_size": TILE_SIZE,
    }
    job_data = {
        'process_graph': json.loads(record["process_graph"]),
        'plan': record.get("plan"),
        'budget': record.get("budget"),
        'title': record.get("title"),
        'description': record.get("description"),
        'variables': variables,
    }
    return _execute_and_wait_for_job(job_data)


def _execute_and_wait_for_job(job_data):
    job_id = JobsPersistence.create(job_data)

    # wait for job to finish:
    period = 0.5  # check every X seconds
    n_checks = int(REQUEST_TIMEOUT/period)
    for _ in range(n_checks):
        job = JobsPersistence.get_by_id(job_id)
        if job["current_status"] in ["finished","error"]:
            break
        time.sleep(0.5)

    JobsPersistence.delete(job_id)

    if job["current_status"] == "finished":
        results = json.loads(job["results"])
        if len(results) != 1:
            return flask.make_response(jsonify(
                id = None,
                code = 400,
                message = "This endpoint can only succeed if process graph yields exactly one result, instead it received: {}.".format(len(results)),
                links = []
                ), 400)

        s3 = boto3.client('s3',
            endpoint_url=S3_LOCAL_URL,
            region_name="eu-central-1",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )

        result = results[0]
        filename = result["filename"]
        object_key = '{}/{}'.format(job_id, os.path.basename(filename))

        s3_object = s3.get_object(Bucket=RESULTS_S3_BUCKET_NAME, Key=object_key)
        content = s3_object['Body'].read()
        response = flask.make_response(content, 200)
        response.mimetype = result["type"]
        return response

    if job["current_status"] == "error":
        return flask.make_response(jsonify(
            id = None,
            code = job["error_code"],
            message = job["error_msg"],
            links = []
        ), job["http_code"])

    return flask.make_response(jsonify(
        id = None,
        code = "Timeout",
        message = "Request timed out.",
        links = []
        ), 408)


@app.route('/collections', methods=['GET'])
def available_collections():
    files = glob.iglob("collection_information/*.json")
    collections = []

    for file in files:
        with open(file) as f:
            data = json.load(f)
            basic_info = {
                "stac_version": data["stac_version"],
                "id": data["id"],
                "description": data["description"],
                "license": data["license"],
                "extent": data["extent"],
                "links": data["links"],
                "title": data.get("title"),
                "keywords": data.get("keywords"),
                "version": data.get("version"),
                "providers": data.get("providers"),
            }
            collections.append(basic_info)

    return flask.make_response(jsonify(
        collections = collections,
        links = []
        ), 200)


@app.route('/collections/<collection_id>', methods=['GET'])
def collection_information(collection_id):
    if not os.path.isfile("collection_information/{}.json".format(collection_id)):
        return flask.make_response(jsonify(
            id = collection_id,
            code = "CollectionNotFound",
            message = 'Collection does not exist.',
            links = []
            ), 404)

    with open("collection_information/{}.json".format(collection_id)) as f:
        collection_information = json.load(f)

    return flask.make_response(collection_information, 200)


@app.route('/processes', methods=['GET'])
def available_processes():
    files = glob.iglob("process_definitions/*.json")
    processes = []
    for file in files:
        with open(file) as f:
            processes.append(json.load(f))

    return flask.make_response(jsonify(
            processes = processes,
            links = [],
        ), 200)


@app.route('/validation', methods=["GET"])
def validate_process_graph():
    data = flask.request.get_json()

    process_graph_schema = PGValidationSchema()
    errors = process_graph_schema.validate(data)

    return {
        "errors": errors,
    }, 200


@app.route('/.well-known/openeo', methods=['GET'])
def well_known():
    return flask.make_response(jsonify(
        versions = [{
            "api_version": "0.4.2",
            "production": False,
            "url": flask.request.url_root
        }]
        ), 200)

if __name__ == '__main__':
    app.run()
