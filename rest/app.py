import datetime
import glob
import json
from logging import log, INFO, WARN, ERROR
import os
import re
import sys
import time
import traceback

import requests
import boto3
import flask
from flask import Flask, url_for, jsonify
from flask_cors import CORS
import beeline
from beeline.middleware.flask import HoneyMiddleware
from sentinelhub import BatchRequestStatus
from pg_to_evalscript import list_supported_processes
from werkzeug.exceptions import HTTPException

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
from processing.processing import (
    check_process_graph_conversion_validity,
    process_data_synchronously,
    create_batch_job,
    start_batch_job,
    get_batch_request_info,
    cancel_batch_job,
    delete_batch_job,
    modify_batch_job,
    get_batch_job_estimate,
)
from processing.utils import inject_variables_in_process_graph
from processing.openeo_process_errors import OpenEOProcessError
from authentication.authentication import authentication_provider
from openeoerrors import (
    OpenEOError,
    AuthenticationRequired,
    AuthenticationSchemeInvalid,
    ProcessUnsupported,
    JobNotFinished,
    JobNotFound,
    JobLocked,
    CollectionNotFound,
    ServiceNotFound,
    Internal,
)
from const import openEOBatchJobStatus

from openeo_collections.collections import collections

app = Flask(__name__)
app.url_map.strict_slashes = False

cors = CORS(
    app,
    origins="*",
    # we can't use '*': https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS/Errors/CORSNotSupportingCredentials
    send_wildcard=False,
    allow_headers=["Authorization", "Accept", "Content-Type"],
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Access-Control-Expose-Headers
    expose_headers=["OpenEO-Costs", "Location", "OpenEO-Identifier"],
    supports_credentials=True,
    max_age=3600,
)

# application performance monitoring:
HONEYCOMP_APM_API_KEY = os.environ.get("HONEYCOMP_APM_API_KEY")
if HONEYCOMP_APM_API_KEY:
    beeline.init(writekey=HONEYCOMP_APM_API_KEY, dataset="OpenEO - rest", service_name="OpenEO")
    HoneyMiddleware(app, db_events=False)  # db_events: we do not use SQLAlchemy


RESULTS_S3_BUCKET_NAME = os.environ.get("RESULTS_S3_BUCKET_NAME", "com.sinergise.openeo.results")
# Zappa allows setting AWS Lambda timeout, but there is CloudFront before Lambda with a default
# timeout of 30 (more like 29) seconds. If we wish to react in time, we need to return in less
# than that.
REQUEST_TIMEOUT = 28

FAKE_AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
FAKE_AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", FAKE_AWS_ACCESS_KEY_ID)
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", FAKE_AWS_SECRET_ACCESS_KEY)
DATA_AWS_ACCESS_KEY_ID = os.environ.get("DATA_AWS_ACCESS_KEY_ID")
DATA_AWS_SECRET_ACCESS_KEY = os.environ.get("DATA_AWS_SECRET_ACCESS_KEY")
S3_LOCAL_URL = os.environ.get("DATA_AWS_S3_ENDPOINT_URL")


STAC_VERSION = "0.9.0"


def update_batch_request_id(job_id, job, new_batch_request_id):
    JobsPersistence.update_key(job_id, "batch_request_id", new_batch_request_id)
    JobsPersistence.update_key(
        job_id,
        "previous_batch_request_ids",
        [*json.loads(job["previous_batch_request_ids"]), job["batch_request_id"]],
    )


@app.errorhandler(OpenEOError)
def openeo_exception_handler(error):
    return flask.make_response(
        jsonify(id=error.record_id, code=error.error_code, message=error.message, links=[]), error.http_code
    )


@app.errorhandler(Exception)
def handle_exception(e):
    # pass through HTTP errors
    log(INFO, f"Error: {str(e)}")
    if isinstance(e, HTTPException):
        return e

    # now you're handling non-HTTP exceptions only
    log(INFO, traceback.format_exc())
    error = Internal(str(e))
    return flask.make_response(
        jsonify(id=error.record_id, code=error.error_code, message=error.message, links=[]), error.http_code
    )


@app.route("/", methods=["GET"])
def api_root():
    return {
        "api_version": "1.0.0",
        "backend_version": os.environ.get("BACKEND_VERSION", "0.0.0").lstrip("v"),
        "stac_version": STAC_VERSION,
        "id": "sentinel-hub-openeo",
        "title": "Sentinel Hub OpenEO",
        "description": "Sentinel Hub OpenEO by [Sinergise](https://sinergise.com)",
        "endpoints": get_endpoints(),
        "billing": {"currency": "processing units"},
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
        url = url.translate(
            str.maketrans(
                {
                    "<": "{",
                    ">": "}",
                }
            )
        )

        endpoints.append(
            {
                "path": url,
                "methods": list(rule.methods - set(["OPTIONS", "HEAD"])),
            }
        )
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
            "title": "Sentinel Hub homepage",
        },
        {
            "href": f"{flask.request.url_root}.well-known/openeo",
            "rel": "version-history",
            "type": "application/json",
            "title": "List of supported openEO versions",
        },
        {
            "href": f"{flask.request.url_root}collections",
            "rel": "data",
            "type": "application/json",
            "title": "List of Datasets",
        },
        {
            "href": "https://docs.sentinel-hub.com/api/latest/api/overview/processing-unit/",
            "rel": "about",
            "type": "text/html",
            "title": "Explanation of processing units",
        },
    ]


@app.route("/credentials/basic", methods=["GET"])
def api_credentials_basic():
    access_token = authentication_provider.check_credentials_basic()
    return flask.make_response(
        jsonify(
            {
                "access_token": access_token,
            }
        ),
        200,
    )


@app.route("/credentials/oidc", methods=["GET"])
def oidc_credentials():
    providers = {"providers": authentication_provider.get_oidc_providers()}
    return flask.make_response(jsonify(providers))


@app.route("/file_formats", methods=["GET"])
def api_file_formats():
    output_formats = {}
    for file in glob.iglob("output_formats/*.json"):
        with open(file) as f:
            output_format = os.path.splitext(os.path.basename(file))[0]
            output_formats[output_format] = json.load(f)

    return flask.make_response(
        jsonify(
            {
                "input": {},
                "output": output_formats,
            }
        ),
        200,
    )


@app.route("/service_types", methods=["GET"])
def api_service_types():
    files = glob.iglob("service_types/*.json")
    result = {}
    for file in files:
        with open(file) as f:
            key = os.path.splitext(os.path.basename(file))[0]
            result[key] = json.load(f)

    return flask.make_response(jsonify(result), 200)


@app.route("/process_graphs", methods=["GET"])
@authentication_provider.with_bearer_auth
def api_process_graphs(user):
    process_graphs = []
    links = []
    for record in ProcessGraphsPersistence.query_by_user_id(user.user_id):
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


@app.route("/process_graphs/<process_graph_id>", methods=["GET", "DELETE", "PUT"])
@authentication_provider.with_bearer_auth
def api_process_graph(process_graph_id, user):
    if flask.request.method in ["GET", "HEAD"]:
        record = ProcessGraphsPersistence.get_by_id(process_graph_id)
        if record is None:
            return flask.make_response(
                jsonify(
                    id=process_graph_id, code="ProcessGraphNotFound", message="Process graph does not exist.", links=[]
                ),
                404,
            )
        return {
            "id": process_graph_id,
            "process_graph": json.loads(record["process_graph"]),
            "summary": record.get("summary"),
            "description": record.get("description"),
        }, 200

    elif flask.request.method == "DELETE":
        ProcessGraphsPersistence.delete(process_graph_id)
        return flask.make_response("The process graph has been successfully deleted.", 204)

    elif flask.request.method == "PUT":
        data = flask.request.get_json()

        process_graph_schema = PutProcessGraphSchema()
        errors = process_graph_schema.validate(data)

        if not re.match(r"^\w+$", process_graph_id):
            errors = "Process graph id does not match the required pattern"

        if errors:
            # Response procedure for validation will depend on how openeo_pg_parser_python will work
            return flask.make_response(jsonify(id=process_graph_id, code=400, message=errors, links=[]), 400)

        data["user_id"] = user.user_id
        ProcessGraphsPersistence.create(data, process_graph_id)

        response = flask.make_response("The user-defined process has been stored successfully.", 200)
        return response


@app.route("/result", methods=["POST"])
@authentication_provider.with_bearer_auth
def api_result():
    if flask.request.method == "POST":
        job_data = flask.request.get_json()

        schema = PostResultSchema()
        errors = schema.validate(job_data)

        if errors:
            log(WARN, "Invalid request: {}".format(errors))
            return flask.make_response(jsonify(id=None, code=400, message=errors, links=[]), 400)

        invalid_node_id = check_process_graph_conversion_validity(job_data["process"]["process_graph"])

        if invalid_node_id is not None:
            error = ProcessUnsupported(invalid_node_id)
            return flask.make_response(
                jsonify(id=None, code=error.error_code, message=error.message, links=[]), error.http_code
            )

        try:
            data, mime_type = process_data_synchronously(job_data["process"])
        except (OpenEOProcessError, OpenEOError) as error:
            raise
        except Exception as error:
            raise Internal(str(error))

        response = flask.make_response(data, 200)
        response.mime_type = mime_type
        response.headers["Content-Type"] = mime_type
        response.headers["OpenEO-Costs"] = None

        return response


@app.route("/jobs", methods=["GET", "POST"])
@authentication_provider.with_bearer_auth
def api_jobs(user):
    if flask.request.method == "GET":
        jobs = []
        links = []

        for record in JobsPersistence.query_by_user_id(user.user_id):
            batch_request_info = get_batch_request_info(record["batch_request_id"])
            jobs.append(
                {
                    "id": record["id"],
                    "title": record.get("title", None),
                    "description": record.get("description", None),
                    "status": openEOBatchJobStatus.from_sentinelhub_batch_job_status(
                        batch_request_info.status, batch_request_info.user_action
                    ).value,
                    "created": record["created"],
                }
            )
            link_to_job = {
                "rel": "related",
                "href": "{}jobs/{}".format(flask.request.url_root, record.get("id")),
            }
            if record.get("title", None):
                link_to_job["title"] = record["title"]
            links.append(link_to_job)

        return {
            "jobs": jobs,
            "links": links,
        }, 200

    elif flask.request.method == "POST":
        data = flask.request.get_json()

        process_graph_schema = PostJobsSchema()
        errors = process_graph_schema.validate(data)

        if errors:
            # Response procedure for validation will depend on how openeo_pg_parser_python will work
            return flask.make_response("Invalid request: {}".format(errors), 400)

        invalid_node_id = check_process_graph_conversion_validity(data["process"]["process_graph"])

        if invalid_node_id is not None:
            raise ProcessUnsupported(invalid_node_id)

        batch_request_id = create_batch_job(data["process"])

        data["batch_request_id"] = batch_request_id
        data["user_id"] = user.user_id

        record_id = JobsPersistence.create(data)

        # add requested headers to 201 response:
        response = flask.make_response("", 201)
        response.headers["Location"] = "/jobs/{}".format(record_id)
        response.headers["OpenEO-Identifier"] = record_id
        return response


@app.route("/jobs/<job_id>", methods=["GET", "PATCH", "DELETE"])
@authentication_provider.with_bearer_auth
def api_batch_job(job_id, user):
    job = JobsPersistence.get_by_id(job_id)
    if job is None or job["user_id"] != user.user_id:
        raise JobNotFound()

    if flask.request.method == "GET":
        batch_request_info = get_batch_request_info(job["batch_request_id"])
        return flask.make_response(
            jsonify(
                id=job_id,
                title=job.get("title", None),
                description=job.get("description", None),
                process={"process_graph": json.loads(job["process"])["process_graph"]},
                status=openEOBatchJobStatus.from_sentinelhub_batch_job_status(
                    batch_request_info.status, batch_request_info.user_action
                ).value,
                error=batch_request_info.error if batch_request_info.status == BatchRequestStatus.FAILED else None,
                created=job["created"],
                updated=job["last_updated"],
            ),
            200,
        )

    elif flask.request.method == "PATCH":
        batch_request_info = get_batch_request_info(job["batch_request_id"])

        if openEOBatchJobStatus.from_sentinelhub_batch_job_status(
            batch_request_info.status, batch_request_info.user_action
        ) in [openEOBatchJobStatus.QUEUED, openEOBatchJobStatus.RUNNING]:
            raise JobLocked()

        data = flask.request.get_json()
        errors = PatchJobsSchema().validate(data)
        if errors:
            # Response procedure for validation will depend on how openeo_pg_parser_python will work
            return flask.make_response(jsonify(id=job_id, code=400, message=errors, links=[]), 400)

        for key in data:
            JobsPersistence.update_key(job_id, key, data[key])

        if data.get("process"):
            new_batch_request_id = modify_batch_job(data["process"])
            update_batch_request_id(job_id, job, new_batch_request_id)

        return flask.make_response("Changes to the job applied successfully.", 204)

    elif flask.request.method == "DELETE":
        s3 = boto3.client(
            "s3",
            endpoint_url=S3_LOCAL_URL,
            region_name="eu-central-1",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )
        res = s3.list_objects_v2(Bucket=RESULTS_S3_BUCKET_NAME, Prefix=f"{job_id}/")
        for obj in res["Contents"]:
            s3.delete_object(Bucket=RESULTS_S3_BUCKET_NAME, Key=obj["Key"])

        JobsPersistence.delete(job_id)
        return flask.make_response("The job has been successfully deleted.", 204)


@app.route("/jobs/<job_id>/results", methods=["POST", "GET", "DELETE"])
@authentication_provider.with_bearer_auth
def add_job_to_queue(job_id, user):
    job = JobsPersistence.get_by_id(job_id)
    if job is None or job["user_id"] != user.user_id:
        raise JobNotFound()

    if flask.request.method == "POST":
        new_batch_request_id = start_batch_job(job["batch_request_id"], json.loads(job["process"]))

        if new_batch_request_id and new_batch_request_id != job["batch_request_id"]:
            update_batch_request_id(job_id, job, new_batch_request_id)

        return flask.make_response("The creation of the resource has been queued successfully.", 202)

    elif flask.request.method == "GET":
        batch_request_info = get_batch_request_info(job["batch_request_id"])

        if batch_request_info.status not in [
            BatchRequestStatus.DONE,
            BatchRequestStatus.FAILED,
            BatchRequestStatus.PARTIAL,
        ]:
            raise JobNotFinished()

        if batch_request_info.status == BatchRequestStatus.FAILED:
            return flask.make_response(
                jsonify(id=job_id, code=424, level="error", message=batch_request_info.error, links=[]), 424
            )

        s3 = boto3.client(
            "s3",
            region_name="eu-central-1",
            aws_access_key_id=DATA_AWS_ACCESS_KEY_ID,
            aws_secret_access_key=DATA_AWS_SECRET_ACCESS_KEY,
        )

        continuation_token = None
        results = []

        while True:
            if continuation_token:
                log(INFO, f"Fetch from bucket")
                response = s3.list_objects_v2(
                    Bucket=RESULTS_S3_BUCKET_NAME, Prefix=job["batch_request_id"], ContinuationToken=continuation_token
                )
            else:
                response = s3.list_objects_v2(Bucket=RESULTS_S3_BUCKET_NAME, Prefix=job["batch_request_id"])
            results.extend(response["Contents"])
            if response["IsTruncated"]:
                continuation_token = response["NextContinuationToken"]
            else:
                break

        assets = {}
        log(INFO, f"Fetched all results: {str(results)}")

        for result in results:
            # create signed url:
            object_key = result["Key"]
            url = s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": RESULTS_S3_BUCKET_NAME,
                    "Key": object_key,
                },
            )
            assets[object_key] = {
                "href": url,
            }

        return flask.make_response(
            jsonify(
                stac_version=STAC_VERSION,
                id=job_id,
                type="Feature",
                geometry=None,
                properties={"datetime": None},
                assets=assets,
                links=[],
            ),
            200,
        )

    elif flask.request.method == "DELETE":
        new_batch_request_id = cancel_batch_job(job["batch_request_id"], json.loads(job["process"]))
        if new_batch_request_id:
            JobsPersistence.update_key(job_id, "batch_request_id", new_batch_request_id)
            JobsPersistence.update_key(
                job_id,
                "previous_batch_request_ids",
                [*json.loads(job["previous_batch_request_ids"]), job["batch_request_id"]],
            )
        return flask.make_response("Processing the job has been successfully canceled.", 204)


@app.route("/jobs/<job_id>/estimate", methods=["GET"])
@authentication_provider.with_bearer_auth
def estimate_job_cost(job_id):
    job = JobsPersistence.get_by_id(job_id)
    if job is None:
        raise JobNotFound()

    estimated_pu, estimated_file_size = get_batch_job_estimate(job["batch_request_id"], json.loads(job["process"]))
    return flask.make_response(
        jsonify(costs=estimated_pu, size=estimated_file_size),
        200,
    )


@app.route("/services", methods=["GET", "POST"])
@authentication_provider.with_bearer_auth
def api_services(user):
    if flask.request.method == "GET":
        services = []
        links = []

        for record in ServicesPersistence.query_by_user_id(user.user_id):
            service_item = {
                "id": record["id"],
                "title": record.get("title", None),
                "description": record.get("description", None),
                "url": "{}service/{}/{}/{{z}}/{{x}}/{{y}}".format(
                    flask.request.url_root, record["service_type"].lower(), record["id"]
                ),
                "type": record["service_type"],
                "enabled": record.get("enabled", True),
                # "created": record["created"],
                "costs": 0,
                "budget": record.get("budget", None),
            }
            if record.get("plan"):
                service_item["plan"] = record["plan"]
            if record.get("configuration") and json.loads(record["configuration"]):
                service_item["configuration"] = json.loads(record["configuration"])
            else:
                service_item["configuration"] = {}

            services.append(service_item)
            links.append(
                {
                    "rel": "related",
                    "href": "{}services/{}".format(flask.request.url_root, record.get("id")),
                }
            )
        return {
            "services": services,
            "links": links,
        }, 200

    elif flask.request.method == "POST":
        data = flask.request.get_json()

        process_graph_schema = PostServicesSchema()
        errors = process_graph_schema.validate(data)
        if errors:
            return flask.make_response("Invalid request: {}".format(errors), 400)

        invalid_node_id = check_process_graph_conversion_validity(data["process"]["process_graph"])

        if invalid_node_id is not None:
            raise ProcessUnsupported(data["process"]["process_graph"][invalid_node_id]["process_id"])

        data["user_id"] = user.user_id
        record_id = ServicesPersistence.create(data)

        # add requested headers to 201 response:
        response = flask.make_response("", 201)
        response.headers["Location"] = "{}services/{}".format(flask.request.url_root, record_id)
        response.headers["OpenEO-Identifier"] = record_id
        return response


@app.route("/services/<service_id>", methods=["GET", "PATCH", "DELETE"])
@authentication_provider.with_bearer_auth
def api_service(service_id, user):
    record = ServicesPersistence.get_by_id(service_id)
    if record is None or record["user_id"] != user.user_id:
        raise ServiceNotFound(service_id)

    if flask.request.method == "GET":
        service = {
            "id": record["id"],
            "title": record.get("title", None),
            "description": record.get("description", None),
            "process": json.loads(record["process"]),
            "url": "{}service/{}/{}/{{z}}/{{x}}/{{y}}".format(
                flask.request.url_root, record["service_type"].lower(), record["id"]
            ),
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

    elif flask.request.method == "PATCH":
        data = flask.request.get_json()
        process_graph_schema = PatchServicesSchema()

        errors = process_graph_schema.validate(data)
        if errors:
            # Response procedure for validation will depend on how openeo_pg_parser_python will work
            return flask.make_response(jsonify(id=service_id, code=400, message=errors, links=[]), 400)

        if data.get("process"):
            invalid_node_id = check_process_graph_conversion_validity(data["process"]["process_graph"])
            if invalid_node_id is not None:
                raise ProcessUnsupported(data["process"]["process_graph"][invalid_node_id]["process_id"])

        for key in data:
            ServicesPersistence.update_key(service_id, key, data[key])

        return flask.make_response("Changes to the service applied successfully.", 204)

    elif flask.request.method == "DELETE":
        ServicesPersistence.delete(service_id)
        return flask.make_response("The service has been successfully deleted.", 204)


@app.route("/service/xyz/<service_id>/<int:zoom>/<int:tx>/<int:ty>", methods=["GET"])
def api_execute_service(service_id, zoom, tx, ty):
    record = ServicesPersistence.get_by_id(service_id)
    if record is None or record["service_type"].lower() != "xyz":
        raise ServiceNotFound(service_id)

    # https://www.maptiler.com/google-maps-coordinates-tile-bounds-projection/
    tile_size = (json.loads(record.get("configuration")) or {}).get("tile_size", 256)
    ty = (2 ** zoom - 1) - ty  # convert from Google Tile XYZ to TMS
    minLat, minLon, maxLat, maxLon = globalmaptiles.GlobalMercator(tileSize=tile_size).TileLatLonBounds(tx, ty, zoom)
    variables = {
        "spatial_extent_west": minLon,
        "spatial_extent_south": minLat,
        "spatial_extent_east": maxLon,
        "spatial_extent_north": maxLat,
    }

    process_info = json.loads(record["process"])

    inject_variables_in_process_graph(process_info["process_graph"], variables)

    try:
        data, mime_type = process_data_synchronously(process_info, width=tile_size, height=tile_size)
    except (OpenEOProcessError, OpenEOError) as error:
        raise
    except Exception as error:
        raise Internal(str(error))

    response = flask.make_response(data, 200)
    response.mimetype = mime_type
    return response


@app.route("/processes", methods=["GET"])
def available_processes():
    files = []
    processes = []

    for supported_process in list_supported_processes():
        files.extend(glob.glob(f"process_definitions/{supported_process}.json"))

    for file in files:
        with open(file) as f:
            processes.append(json.load(f))

    processes.sort(key=lambda process: process["id"])

    return flask.make_response(
        jsonify(
            processes=processes,
            links=[],
        ),
        200,
    )


@app.route("/collections", methods=["GET"])
def available_collections():

    all_collections = collections.get_collections_basic_info()
    return flask.make_response(jsonify(collections=all_collections, links=[]), 200)


@app.route("/collections/<collection_id>", methods=["GET"])
def collection_information(collection_id):
    collection = collections.get_collection(collection_id)

    if not collection:
        raise CollectionNotFound()

    return flask.make_response(collection, 200)


@app.route("/validation", methods=["POST"])
def validate_process_graph():
    data = flask.request.get_json()

    process_graph_schema = PGValidationSchema()
    errors = process_graph_schema.validate(data)

    validation_errors = []

    if errors.get("process_graph"):
        for error in errors.get("process_graph"):
            validation_errors.append({"message": error, "code": "ValidationError"})

    return {
        "errors": validation_errors,
    }, 200


@app.route("/.well-known/openeo", methods=["GET"])
def well_known():
    return flask.make_response(
        jsonify(versions=[{"api_version": "1.0.0", "production": False, "url": flask.request.url_root}]), 200
    )


if __name__ == "__main__":
    # if you need to run this app under HTTPS, install pyOpenSSL
    # (`pip install pyOpenSSL`) and replace app.run with this line:
    if sys.argv[1:] == ["https"]:
        print("Running as HTTPS!")
        app.run(ssl_context="adhoc")
    else:
        app.run()
