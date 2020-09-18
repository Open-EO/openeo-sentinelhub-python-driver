import datetime
import glob
import json
from logging import log, INFO, WARN
import os
import re
import sys
import time

import requests
import boto3
import flask
from flask import Flask, url_for, jsonify
from flask_cors import CORS
import beeline
from beeline.middleware.flask import HoneyMiddleware

import globalmaptiles
from schemas import (
    PutProcessGraphSchema,
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

# application performance monitoring:
HONEYCOMP_APM_API_KEY = os.environ.get('HONEYCOMP_APM_API_KEY')
if HONEYCOMP_APM_API_KEY:
    beeline.init(writekey=HONEYCOMP_APM_API_KEY, dataset='OpenEO - rest', service_name='OpenEO')
    HoneyMiddleware(app, db_events=False) # db_events: we do not use SQLAlchemy


RESULTS_S3_BUCKET_NAME = os.environ.get('RESULTS_S3_BUCKET_NAME', 'com.sinergise.openeo.results')
# Zappa allows setting AWS Lambda timeout, but there is CloudFront before Lambda with a default
# timeout of 30 (more like 29) seconds. If we wish to react in time, we need to return in less
# than that.
REQUEST_TIMEOUT = 28

FAKE_AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
FAKE_AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', FAKE_AWS_ACCESS_KEY_ID)
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', FAKE_AWS_SECRET_ACCESS_KEY)
S3_LOCAL_URL = os.environ.get('DATA_AWS_S3_ENDPOINT_URL')

STAC_VERSION = "0.9.0"

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
        "api_version": "1.0.0",
        "backend_version": os.environ.get('BACKEND_VERSION', "0.0.0").lstrip('v'),
        "stac_version": STAC_VERSION,
        "id": "sentinel-hub-openeo",
        "title": "Sentinel Hub OpenEO",
        "description": "Sentinel Hub OpenEO by [Sinergise](https://sinergise.com)",
        "endpoints": get_endpoints(),
        "links": get_links(),
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

def get_links():
    """
        Returns a list of links related to this service.
    """
    return [
        {
            "href": "https://www.sentinel-hub.com/",
            "rel": "about",
            "type": "text/html",
            "title": "Sentinel Hub homepage"
        },
        {
            "href": f"{flask.request.url_root}.well-known/openeo",
            "rel": "version-history",
            "type": "application/json",
            "title": "List of supported openEO versions"
        },
        {
            "href": f"{flask.request.url_root}collections",
            "rel": "data",
            "type": "application/json",
            "title": "List of Datasets"
        }
    ]


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


@app.route('/process_graphs', methods=["GET"])
def api_process_graphs():
    process_graphs = []
    links = []
    for record in ProcessGraphsPersistence.items():
        process_item = {
            "id": record["id"],
        }
        if record.get("description"):
            # It's supposed to be nullable, but validator disagrees
            process_item["description"] = record.get("description")
        if record.get("summary"):
            # It's supposed to be nullable, but validator disagrees
            process_item["summary"] = record.get("summary")
        if record.get("returns"):
            # It's supposed to be nullable, but validator disagrees
            process_item["returns"] = record.get("returns")
        if record.get("parameters"):
            # It's supposed to be nullable, but validator disagrees
            process_item["parameters"] = record.get("parameters")
        if record.get("categories"):
            process_item["categories"] = record.get("categories")
        if record.get("deprecated"):
            process_item["deprecated"] = record.get("deprecated")
        if record.get("experimental"):
            process_item["experimental"] = record.get("experimental")

        process_graphs.append(process_item)

        link_to_pg = {
            "rel": "related",
            "href": "{}/process_graphs/{}".format(flask.request.url_root, record["id"]),
        }
        if record.get("title", None):
            link_to_pg["title"] = record["title"]
        links.append(link_to_pg)
    return {
        "processes": process_graphs,
        "links": links,
    }, 200


@app.route('/process_graphs/<process_graph_id>', methods=["GET", "DELETE", "PUT"])
def api_process_graph(process_graph_id):
    if flask.request.method in ['GET', 'HEAD']:
        record = ProcessGraphsPersistence.get_by_id(process_graph_id)
        if record is None:
            return flask.make_response(jsonify(
                id = process_graph_id,
                code = "ProcessGraphNotFound",
                message = "Process graph does not exist.",
                links = []
                ), 404)
        return {
            "id": process_graph_id,
            "process_graph": json.loads(record["process_graph"]),
            "summary": record.get("summary"),
            "description": record.get("description"),
        }, 200

    elif flask.request.method == 'DELETE':
        ProcessGraphsPersistence.delete(process_graph_id)
        return flask.make_response('The process graph has been successfully deleted.', 204)

    elif flask.request.method == 'PUT':
        data = flask.request.get_json()

        process_graph_schema = PutProcessGraphSchema()
        errors = process_graph_schema.validate(data)

        if not re.match(r'^\w+$', process_graph_id):
            errors = "Process graph id does not match the required pattern";

        if errors:
            # Response procedure for validation will depend on how openeo_pg_parser_python will work
            return flask.make_response(jsonify(
                id = process_graph_id,
                code = 400,
                message = errors,
                links = []
                ), 400)

        ProcessGraphsPersistence.create(data, process_graph_id)

        response = flask.make_response('The user-defined process has been stored successfully.', 200)
        return response


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
                "status": record["current_status"],
                "created": record["created"]
            })
            link_to_job = {
                "rel": "related",
                "href": "{}/jobs/{}".format(flask.request.url_root, record.get("id")),
            }
            if record.get("title", None):
                link_to_job["title"] = record["title"]
            links.append(link_to_job)

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

        data["current_status"] = "created"
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
            process = {
                "process_graph": json.loads(job["process"])["process_graph"]
            },
            status = status,  # "status" is reserved word in DynamoDB
            error = job["error_msg"] if status == "error" else None,
            created = job["created"],
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
        errors = PatchJobsSchema().validate(data)
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
        JobsPersistence.update_status(job_id, "created")

        return flask.make_response('Changes to the job applied successfully.', 204)

    elif flask.request.method == 'DELETE':
        # for queued and running jobs, we need to mark them to be cancelled and wait for their status to change:
        if job["current_status"] in ["queued", "running"]:
            JobsPersistence.set_should_be_cancelled(job_id)

            # wait for job to get status 'cancelled':
            period = 0.5  # check every X seconds
            n_checks = int(REQUEST_TIMEOUT/period)
            for _ in range(n_checks):
                job = JobsPersistence.get_by_id(job_id)
                if job["current_status"] not in ["queued", "running"]:
                    break
                time.sleep(period)
            if job["current_status"] in ["queued", "running"]:
                return flask.make_response('Could not stop the job properly.', 500)

        JobsPersistence.delete(job_id)
        return flask.make_response('The job has been successfully deleted.', 204)


@app.route('/jobs/<job_id>/results', methods=['POST','GET','DELETE'])
def add_job_to_queue(job_id):
    if flask.request.method == "POST":
        job = JobsPersistence.get_by_id(job_id)

        if job["current_status"] in ["created", "finished", "canceled", "error"]:
            JobsPersistence.update_status(job_id, "queued")
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
                level = "error",
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
                'rel': "related",
                'href': url,
                'type': mime_type,
            })

        return flask.make_response(jsonify(
                stac_version = STAC_VERSION,
                id = job_id,
                type = "Feature",
                geometry = None,
                properties = {"datetime": None},
                assets = {},
                links = links,
            ), 200)

    elif flask.request.method == "DELETE":
        job = JobsPersistence.get_by_id(job_id)

        JobsPersistence.set_should_be_cancelled(job_id)

        period = 0.5  # check every X seconds
        n_checks = int(REQUEST_TIMEOUT/period)
        for _ in range(n_checks):
            job = JobsPersistence.get_by_id(job_id)
            if job["current_status"] not in ["queued", "running"]:
                return flask.make_response('Processing the job has been successfully canceled.', 204)
            time.sleep(period)

        return flask.make_response('Could not cancel the job properly.', 500)


@app.route('/services', methods=['GET','POST'])
def api_services():
    if flask.request.method == 'GET':
        services = []
        links = []

        for record in ServicesPersistence.items():
            service_item = {
                "id": record["id"],
                "title": record.get("title", None),
                "description": record.get("description", None),
                "url": "{}service/{}/{}/{{z}}/{{x}}/{{y}}".format(flask.request.url_root, record["service_type"].lower(), record["id"]),
                "type": record["service_type"],
                "enabled": record.get("enabled", True),
                "costs": 0,
                "budget": record.get("budget", None),
            }
            if record.get("plan"):
                service_item["plan"] = record["plan"],
            if record.get("configuration") and json.loads(record["configuration"]):
                service_item["configuration"] = json.loads(record["configuration"])
            else:
                service_item["configuration"] = {}

            services.append(service_item)
            links.append({
                "rel": "related",
                "href": "{}services/{}".format(flask.request.url_root, record.get("id")),
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
        service = {
            "id": record["id"],
            "title": record.get("title", None),
            "description": record.get("description", None),
            "process": json.loads(record["process"]),
            "url": "{}service/{}/{}/{{z}}/{{x}}/{{y}}".format(flask.request.url_root, record["service_type"].lower(), record["id"]),
            "type": record["service_type"],
            "enabled": record.get("enabled", True),
            "attributes": {},
            "created": record["created"],
            "costs": 0,
            "budget": record.get("budget", None),
        }
        if record.get("plan"):
            service["plan"] = record["plan"]
        if record.get("configuration") and json.loads(record["configuration"]):
            service["configuration"] = json.loads(record["configuration"])
        else:
            service["configuration"] = {}
        return flask.make_response(jsonify(service), 200)

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
    ty = (2**zoom - 1) - ty  # convert from Google Tile XYZ to TMS
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
        'process': json.loads(record["process"]),
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
    with beeline.tracer("waiting for workers"):
        period = 0.5  # check every X seconds
        n_checks = int(REQUEST_TIMEOUT/period)
        for _ in range(n_checks):
            job = JobsPersistence.get_by_id(job_id)
            if job["current_status"] in ["finished","error"]:
                break
            time.sleep(period)

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


@app.route('/validation', methods=["POST"])
def validate_process_graph():
    data = flask.request.get_json()

    process_graph_schema = PGValidationSchema()
    errors = process_graph_schema.validate(data)

    validation_errors = []

    if errors.get("process_graph"):
        for error in errors.get("process_graph"):
            validation_errors.append({
                "message": error,
                "code": "ValidationError"
            })

    return {
        "errors": validation_errors,
    }, 200


@app.route('/.well-known/openeo', methods=['GET'])
def well_known():
    return flask.make_response(jsonify(
        versions = [{
            "api_version": "1.0.0",
            "production": False,
            "url": flask.request.url_root
        }]
        ), 200)

if __name__ == '__main__':
    # if you need to run this app under HTTPS, install pyOpenSSL
    # (`pip install pyOpenSSL`) and replace app.run with this line:
    if sys.argv[1:] == ['https']:
        print("Running as HTTPS!")
        app.run(ssl_context='adhoc')
    else:
        app.run()
