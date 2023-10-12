import glob
import json

from logging import log, INFO, WARN
import os
import re
import sys
import uuid
from datetime import datetime, timedelta

import flask
from flask import Flask, jsonify, g
from flask_cors import CORS
import beeline
from beeline.middleware.flask import HoneyMiddleware
from pg_to_evalscript import list_supported_processes
from werkzeug.exceptions import HTTPException
from urllib.parse import urlparse, parse_qs

import globalmaptiles
from logs.logging import with_logging
from schemas import (
    PutProcessGraphSchema,
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
    cancel_batch_job,
    modify_batch_job,
    get_batch_job_estimate,
    get_batch_job_status,
)
from processing.utils import inject_variables_in_process_graph, overwrite_spatial_extent_without_parameters
from processing.openeo_process_errors import OpenEOProcessError
from authentication.authentication import authentication_provider
from openeoerrors import (
    OpenEOError,
    ProcessUnsupported,
    JobNotFinished,
    JobNotFound,
    JobLocked,
    CollectionNotFound,
    ServiceNotFound,
    Internal,
    BadRequest,
    ProcessGraphNotFound,
    SHOpenEOError,
)
from authentication.user import User
from const import openEOBatchJobStatus, optional_process_parameters, SentinelHubBillingPlan
from utils import get_all_process_definitions, convert_timestamp_to_simpler_format, get_roles, ISO8601_UTC_FORMAT
from buckets import get_bucket

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


def get_all_user_defined_processes():
    all_user_defined_processes = dict()
    for record in ProcessGraphsPersistence.query_by_user_id(g.user.user_id):
        all_user_defined_processes[record["id"]] = record["process_graph"]
    return all_user_defined_processes


# application performance monitoring:
HONEYCOMP_APM_API_KEY = os.environ.get("HONEYCOMP_APM_API_KEY")
if HONEYCOMP_APM_API_KEY:
    beeline.init(writekey=HONEYCOMP_APM_API_KEY, dataset="OpenEO - rest", service_name="OpenEO")
    HoneyMiddleware(app, db_events=False)  # db_events: we do not use SQLAlchemy


STAC_VERSION = "1.0.0"


def update_batch_request_id(job_id, job, new_batch_request_id):
    JobsPersistence.update_key(job_id, "batch_request_id", new_batch_request_id)
    JobsPersistence.update_key(
        job_id,
        "previous_batch_request_ids",
        [*json.loads(job["previous_batch_request_ids"]), job["batch_request_id"]],
    )


@app.before_request
def add_uuid_to_request():
    flask.request.req_id = uuid.uuid4()


@app.errorhandler(OpenEOError)
@with_logging
def openeo_exception_handler(error):
    return flask.make_response(
        jsonify(id=error.record_id, code=error.error_code, message=error.message, links=[]), error.http_code
    )


@app.errorhandler(Exception)
@with_logging
def handle_exception(e):
    # pass through HTTP errors
    if isinstance(e, HTTPException):
        return e

    # now you're handling non-HTTP exceptions only
    if not issubclass(type(e), (OpenEOError, OpenEOProcessError, SHOpenEOError)):
        e = Internal(str(e))

    return flask.make_response(jsonify(id=e.record_id, code=e.error_code, message=e.message, links=[]), e.http_code)


@app.route("/", methods=["GET"])
@with_logging
def api_root():
    return {
        "api_version": "1.0.0",
        "backend_version": os.environ.get("BACKEND_VERSION", "0.0.0").lstrip("v"),
        "stac_version": STAC_VERSION,
        "id": "sentinel-hub-openeo",
        "title": "Sentinel Hub OpenEO",
        "description": "Sentinel Hub OpenEO by [Sinergise](https://sinergise.com)",
        "endpoints": get_endpoints(),
        "billing": {
            "currency": "processing units",
            "default_plan": SentinelHubBillingPlan.TRIAL.name,
            "plans": [
                {"name": plan.name, "description": plan.description, "paid": plan.is_paid, "url": plan.url}
                for plan in SentinelHubBillingPlan
            ],
        },
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
@with_logging
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
@with_logging
def oidc_credentials():
    providers = {"providers": authentication_provider.get_oidc_providers()}
    return flask.make_response(jsonify(providers))


@app.route("/me", methods=["GET"])
@authentication_provider.with_bearer_auth
def describe_account():
    return flask.make_response(jsonify(g.user.get_user_info()), 200)


@app.route("/file_formats", methods=["GET"])
@with_logging
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
@with_logging
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
@with_logging
def api_process_graphs():
    process_graphs = []
    links = []
    for record in ProcessGraphsPersistence.query_by_user_id(g.user.user_id):
        # We don't return process_graph and only return explicitly set optional values as documentation states:
        # > It is strongly RECOMMENDED to keep the response size small by omitting larger optional values from the objects
        process_item = {
            "id": record["id"],
        }

        for attr in optional_process_parameters:
            if record.get(attr) is not None:
                process_item[attr] = record[attr]

        process_graphs.append(process_item)

        link_to_pg = {
            "rel": "related",
            "href": "{}/process_graphs/{}".format(flask.request.url_root, record["id"]),
        }
        links.append(link_to_pg)
    return {
        "processes": process_graphs,
        "links": links,
    }, 200


@app.route("/process_graphs/<process_graph_id>", methods=["GET", "DELETE", "PUT"])
@authentication_provider.with_bearer_auth
@with_logging
def api_process_graph(process_graph_id):
    if flask.request.method in ["GET", "HEAD"]:
        record = ProcessGraphsPersistence.get_by_id(process_graph_id)
        if record is None:
            raise ProcessGraphNotFound()

        process_item = {
            "id": record["id"],
            "process_graph": record["process_graph"],
        }
        for attr in optional_process_parameters:
            process_item[attr] = record.get(attr)

        if process_item["deprecated"] is None:
            process_item["deprecated"] = False
        if process_item["experimental"] is None:
            process_item["experimental"] = False
        if process_item["categories"] is None:
            process_item["categories"] = []
        if process_item["exceptions"] is None:
            process_item["exceptions"] = {}
        if process_item["examples"] is None:
            process_item["examples"] = []
        if process_item["links"] is None:
            process_item["links"] = []

        return process_item, 200

    elif flask.request.method == "DELETE":
        ProcessGraphsPersistence.delete(process_graph_id)
        return flask.make_response("The process graph has been successfully deleted.", 204)

    elif flask.request.method == "PUT":
        data = flask.request.get_json()

        if not re.match(r"^\w+$", process_graph_id):
            raise BadRequest("Process graph id does not match the required pattern")

        process_graph_schema = PutProcessGraphSchema()
        errors = process_graph_schema.validate(data)

        if errors:
            if isinstance(errors, dict):
                if errors.get("_schema"):
                    raise BadRequest(errors.get("_schema"))

        if "id" in data and data["id"] != process_graph_id:
            data["id"] = process_graph_id

        if process_graph_id in list_supported_processes():
            raise BadRequest(f"Process with id '{process_graph_id}' already exists among pre-defined processes.")

        data["user_id"] = g.user.user_id
        ProcessGraphsPersistence.create(data, process_graph_id)

        return flask.make_response("The user-defined process has been stored successfully.", 200)


@app.route("/result", methods=["POST"])
@authentication_provider.with_bearer_auth
@with_logging
def api_result():
    if flask.request.method == "POST":
        job_data = flask.request.get_json()

        schema = PostResultSchema()
        errors = schema.validate(job_data)

        if errors:
            if errors.get("process").get("process_graph"):
                return flask.make_response(
                    jsonify(id=None, code=400, message=errors.get("process").get("process_graph")[0], links=[]), 400
                )

        invalid_node_id = check_process_graph_conversion_validity(job_data["process"]["process_graph"])

        if invalid_node_id is not None:
            error = ProcessUnsupported(invalid_node_id)
            return flask.make_response(
                jsonify(id=None, code=error.error_code, message=error.message, links=[]), error.http_code
            )

        data, mime_type = process_data_synchronously(job_data["process"])

        response = flask.make_response(data, 200)
        response.mime_type = mime_type
        response.headers["Content-Type"] = mime_type
        response.headers["OpenEO-Costs"] = None

        return response


@app.route("/jobs", methods=["GET", "POST"])
@authentication_provider.with_bearer_auth
@with_logging
def api_jobs():
    if flask.request.method == "GET":
        jobs = []
        links = []

        for record in JobsPersistence.query_by_user_id(g.user.user_id):
            status, _ = get_batch_job_status(record["batch_request_id"], record["deployment_endpoint"])

            jobs.append(
                {
                    "id": record["id"],
                    "title": record.get("title", None),
                    "description": record.get("description", None),
                    "status": status.value,
                    "created": convert_timestamp_to_simpler_format(record["created"]),
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
            if errors.get("process").get("process_graph"):
                return flask.make_response(
                    jsonify(id=None, code=400, message=errors.get("process").get("process_graph")[0], links=[]), 400
                )

        invalid_node_id = check_process_graph_conversion_validity(data["process"]["process_graph"])

        if invalid_node_id is not None:
            raise ProcessUnsupported(invalid_node_id)

        batch_request_id, deployment_endpoint = create_batch_job(data["process"])

        estimated_pu, estimated_file_size = get_batch_job_estimate(batch_request_id, data["process"], deployment_endpoint)
    
        data["batch_request_id"] = batch_request_id
        data["user_id"] = g.user.user_id
        data["deployment_endpoint"] = deployment_endpoint
        data["estimated_pu"] = str(estimated_pu)
        data["estimated_file_size"] = str(estimated_file_size)

        record_id = JobsPersistence.create(data)

        # add requested headers to 201 response:
        response = flask.make_response("", 201)
        response.headers["Location"] = "/jobs/{}".format(record_id)
        response.headers["OpenEO-Identifier"] = record_id
        return response


@app.route("/jobs/<job_id>", methods=["GET", "PATCH", "DELETE"])
@authentication_provider.with_bearer_auth
@with_logging
def api_batch_job(job_id):
    job = JobsPersistence.get_by_id(job_id)
    if job is None or job["user_id"] != g.user.user_id:
        raise JobNotFound()

    if flask.request.method == "GET":
        status, error = get_batch_job_status(job["batch_request_id"], job["deployment_endpoint"])
        return flask.make_response(
            jsonify(
                id=job_id,
                title=job.get("title", None),
                description=job.get("description", None),
                process={"process_graph": json.loads(job["process"])["process_graph"]},
                status=status.value,
                error=error,
                created=convert_timestamp_to_simpler_format(job["created"]),
                updated=convert_timestamp_to_simpler_format(job["last_updated"]),
                costs=float(job.get("estimated_pu", 0)) * 0.15,
                usage={"Platform Credits": {"unit": "credits", "value": float(job.get("estimated_pu", 0)) * 0.15},
                       "Sentinel Hub": {"unit": "sentinelhub_processing_unit", "value": float(job.get("estimated_pu", 0))}}
            ),
            200,
        )

    elif flask.request.method == "PATCH":
        status, _ = get_batch_job_status(job["batch_request_id"], job["deployment_endpoint"])

        if status in [openEOBatchJobStatus.QUEUED, openEOBatchJobStatus.RUNNING]:
            raise JobLocked()

        data = flask.request.get_json()
        errors = PatchJobsSchema().validate(data)
        if errors:
            if errors.get("process").get("process_graph"):
                return flask.make_response(
                    jsonify(id=None, code=400, message=errors.get("process").get("process_graph")[0], links=[]), 400
                )

        if data.get("process"):
            new_batch_request_id, deployment_endpoint = modify_batch_job(data["process"])
            update_batch_request_id(job_id, job, new_batch_request_id)
            data["deployment_endpoint"] = deployment_endpoint

        for key in data:
            JobsPersistence.update_key(job_id, key, data[key])

        return flask.make_response("Changes to the job applied successfully.", 204)

    elif flask.request.method == "DELETE":
        bucket = get_bucket(job["deployment_endpoint"])
        results = bucket.get_data_from_bucket(prefix=job["batch_request_id"])
        bucket.delete_objects(results)

        JobsPersistence.delete(job_id)
        return flask.make_response("The job has been successfully deleted.", 204)


@app.route("/jobs/<job_id>/results", methods=["POST", "GET", "DELETE"])
@authentication_provider.with_bearer_auth
@with_logging
def add_job_to_queue(job_id):
    job = JobsPersistence.get_by_id(job_id)
    if job is None or job["user_id"] != g.user.user_id:
        raise JobNotFound()

    if flask.request.method == "POST":
        new_batch_request_id = start_batch_job(
            job["batch_request_id"], json.loads(job["process"]), job["deployment_endpoint"], job_id
        )

        if new_batch_request_id and new_batch_request_id != job["batch_request_id"]:
            update_batch_request_id(job_id, job, new_batch_request_id)

        # can we create a /results_metadata.json file already here?
        # we don't have the contents of the folder yet to create presigned URLs
        # also, how does SH batch API handle already existing folder in the bucket?

        return flask.make_response("The creation of the resource has been queued successfully.", 202)

    elif flask.request.method == "GET":
        status, error = get_batch_job_status(job["batch_request_id"], job["deployment_endpoint"])

        if status not in [
            openEOBatchJobStatus.FINISHED,
            openEOBatchJobStatus.ERROR,
        ]:
            raise JobNotFinished()

        if status == openEOBatchJobStatus.ERROR:
            return flask.make_response(jsonify(id=job_id, code=424, level="error", message=error, links=[]), 424)

        bucket = get_bucket(job["deployment_endpoint"])

        # naively generate dummy metadata.json in the bucket so that it will already be
        # in the response of first bucket.get_data_from_bucket() call
        # and the code for generating presigned urls can stay the same
        metadata_filename = "metadata.json"
        bucket.put_file_to_bucket("", prefix=job["batch_request_id"], file_name=metadata_filename)

        results = bucket.get_data_from_bucket(prefix=job["batch_request_id"])
        log(INFO, f"Fetched all results: {str(results)}")

        assets = {}
        links = []
        metadata_valid = None
        for result in results:

            # do not add json file created by SH batch job API to the list of assets
            sh_batch_job_json_filename = f"request-{job['batch_request_id']}.json"
            if sh_batch_job_json_filename in result["Key"]:
                continue

            # create signed url:
            object_key = result["Key"]
            url = bucket.generate_presigned_url(object_key=object_key)

            parsed_url = urlparse(url)
            parsed_query = parse_qs(parsed_url.query)
            time_url_generated = datetime.strptime(parsed_query["X-Amz-Date"][0], "%Y%m%dT%H%M%SZ")
            time_expires = timedelta(seconds=int(parsed_query["X-Amz-Expires"][0]))
            time_valid = time_url_generated + time_expires
            time_valid_iso8601 = time_valid.strftime(ISO8601_UTC_FORMAT)

            # add signed url (that links to metadata) to links with rel type "canonical"
            if metadata_filename in result["Key"]:
                metadata_valid = time_valid_iso8601
                links.append(
                    {"href": url, "rel": "canonical", "type": "application/json", "expires": time_valid_iso8601}
                )
            else:
                roles = get_roles(object_key)
                assets[object_key] = {"href": url, "roles": roles, "expires": time_valid_iso8601}

        # we can create a /results_metadata.json file here
        # the contents of the batch job folder in the bucket isn't revealed anywhere else anyway
        metadata_creation_time = datetime.utcnow().strftime(ISO8601_UTC_FORMAT)
        batch_job_metadata = {
            "type": "Feature",
            "stac_version": STAC_VERSION,
            "stac_extensions": [
                "https://stac-extensions.github.io/processing/v1.1.0/schema.json",
                "https://stac-extensions.github.io/timestamps/v1.1.0/schema.json",
            ],
            "id": job_id,
            "geometry": None,
            "properties": {
                "title": job.get("title", None),
                "datetime": metadata_creation_time,
                "expires": metadata_valid,
                "usage": {
                    "Platform credits": {"unit": "credits", "value": float(job["estimated_pu"]) * 0.15},
                    "Sentinel Hub": {"unit": "sentinelhub_processing_unit", "value": float(job["estimated_pu"])},
                },
                "processing:expression": {"format": "openeo", "expression": json.loads(job["process"])},
            },
            "links": links,
            "assets": assets,
        }

        # boto3 put_object() used in this method simply overwrites existing file
        # no need to check if file already exists
        bucket.put_file_to_bucket(
            json.dumps(batch_job_metadata), prefix=job["batch_request_id"], file_name=metadata_filename
        )

        return flask.make_response(jsonify(batch_job_metadata), 200)

    elif flask.request.method == "DELETE":
        new_batch_request_id, _ = cancel_batch_job(
            job["batch_request_id"], json.loads(job["process"]), job["deployment_endpoint"]
        )
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
@with_logging
def estimate_job_cost(job_id):
    job = JobsPersistence.get_by_id(job_id)
    if job is None:
        raise JobNotFound()
    
    estimated_pu = float(job["estimated_pu"])
    estimated_file_size = float(job["estimated_file_size"])

    return flask.make_response(
        jsonify(costs=estimated_pu, size=estimated_file_size),
        200,
    )


@app.route("/services", methods=["GET", "POST"])
@authentication_provider.with_bearer_auth
@with_logging
def api_services():
    if flask.request.method == "GET":
        services = []
        links = []

        for record in ServicesPersistence.query_by_user_id(g.user.user_id):
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
            if errors.get("process").get("process_graph"):
                return flask.make_response(
                    jsonify(id=None, code=400, message=errors.get("process").get("process_graph")[0], links=[]), 400
                )

        invalid_node_id = check_process_graph_conversion_validity(data["process"]["process_graph"])
        data["process"]["process_graph"] = overwrite_spatial_extent_without_parameters(data["process"]["process_graph"])

        if invalid_node_id is not None:
            raise ProcessUnsupported(data["process"]["process_graph"][invalid_node_id]["process_id"])

        data["user_id"] = g.user.user_id
        record_id = ServicesPersistence.create(data)

        # add requested headers to 201 response:
        response = flask.make_response("", 201)
        response.headers["Location"] = "{}services/{}".format(flask.request.url_root, record_id)
        response.headers["OpenEO-Identifier"] = record_id
        return response


@app.route("/services/<service_id>", methods=["GET", "PATCH", "DELETE"])
@authentication_provider.with_bearer_auth
@with_logging
def api_service(service_id):
    record = ServicesPersistence.get_by_id(service_id)
    if record is None or record["user_id"] != g.user.user_id:
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
            "created": convert_timestamp_to_simpler_format(record["created"]),
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
            if errors.get("process").get("process_graph"):
                return flask.make_response(
                    jsonify(id=None, code=400, message=errors.get("process").get("process_graph")[0], links=[]), 400
                )

        if data.get("process"):
            invalid_node_id = check_process_graph_conversion_validity(data["process"]["process_graph"])
            if invalid_node_id is not None:
                raise ProcessUnsupported(data["process"]["process_graph"][invalid_node_id]["process_id"])
            data["process"]["process_graph"] = overwrite_spatial_extent_without_parameters(
                data["process"]["process_graph"]
            )

        for key in data:
            ServicesPersistence.update_key(service_id, key, data[key])

        return flask.make_response("Changes to the service applied successfully.", 204)

    elif flask.request.method == "DELETE":
        ServicesPersistence.delete(service_id)
        return flask.make_response("The service has been successfully deleted.", 204)


@app.route("/service/xyz/<service_id>/<int:zoom>/<int:tx>/<int:ty>", methods=["GET"])
@with_logging
def api_execute_service(service_id, zoom, tx, ty):
    record = ServicesPersistence.get_by_id(service_id)
    if record is None or record["service_type"].lower() != "xyz":
        raise ServiceNotFound(service_id)

    # XYZ does not require authentication, however we need user_id to support user-defined processes
    g.user = User(user_id=record["user_id"])

    # https://www.maptiler.com/google-maps-coordinates-tile-bounds-projection/
    tile_size = (json.loads(record.get("configuration")) or {}).get("tile_size", 256)
    ty = (2**zoom - 1) - ty  # convert from Google Tile XYZ to TMS
    minLat, minLon, maxLat, maxLon = globalmaptiles.GlobalMercator(tileSize=tile_size).TileLatLonBounds(tx, ty, zoom)
    variables = {
        "spatial_extent_west": minLon,
        "spatial_extent_south": minLat,
        "spatial_extent_east": maxLon,
        "spatial_extent_north": maxLat,
    }

    process_info = json.loads(record["process"])

    inject_variables_in_process_graph(process_info["process_graph"], variables)

    data, mime_type = process_data_synchronously(process_info, width=tile_size, height=tile_size)

    response = flask.make_response(data, 200)
    response.mimetype = mime_type
    return response


@app.route("/processes", methods=["GET"])
@with_logging
def available_processes():
    processes = get_all_process_definitions()
    processes.sort(key=lambda process: process["id"])

    return flask.make_response(
        jsonify(
            processes=processes,
            links=[],
        ),
        200,
    )


@app.route("/collections", methods=["GET"])
@with_logging
def available_collections():
    all_collections = collections.get_collections_basic_info()
    return flask.make_response(jsonify(collections=all_collections, links=[]), 200)


@app.route("/collections/<collection_id>", methods=["GET"])
@with_logging
def collection_information(collection_id):
    collection = collections.get_collection(collection_id)

    if not collection:
        raise CollectionNotFound()

    return flask.make_response(collection, 200)


@app.route("/validation", methods=["POST"])
@with_logging
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
@with_logging
def well_known():
    return flask.make_response(
        jsonify(versions=[{"api_version": "1.0.0", "production": False, "url": flask.request.url_root}]), 200
    )


@app.route("/health", methods=["GET"])
@with_logging
def return_health():
    return flask.make_response({"status": "OK"}, 200)


if __name__ == "__main__":
    # if you need to run this app under HTTPS, install pyOpenSSL
    # (`pip install pyOpenSSL`) and replace app.run with this line:
    if sys.argv[1:] == ["https"]:
        print("Running as HTTPS!")
        app.run(ssl_context="adhoc")
    else:
        app.run(debug=True)
