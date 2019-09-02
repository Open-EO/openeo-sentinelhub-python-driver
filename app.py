import flask
from flask import Flask, url_for, jsonify
from flask_marshmallow import Marshmallow
import os
from schemas import PostProcessGraphsSchema, PostJobsSchema, PostResultSchema, PGValidationSchema
import datetime
import requests
from logging import log, INFO, WARN
import json
import boto3

from dynamodb import Persistence


app = Flask(__name__)
app.url_map.strict_slashes = False


URL_ROOT = os.environ.get('URL_ROOT', '').rstrip('/')
RESULTS_S3_BUCKET_NAME = os.environ.get('RESULTS_S3_BUCKET_NAME', 'com.sinergise.openeo.results')


@app.route('/', methods=["GET"])
def api_root():
    return {
        "api_version": "0.4.1",
        "backend_version": "0.0.1",
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

        endpoints.append({
            "path": url,
            "methods": list(rule.methods - set(["OPTIONS", "HEAD"])),
        })
    return endpoints

@app.route('/process_graphs', methods=["GET", "POST"])
@app.route('/process_graphs/<process_graph_id>', methods=["GET", "DELETE", "PATCH"])
def api_process_graphs(process_graph_id=None):
    if flask.request.method in ['GET', 'HEAD']:
        if process_graph_id is None:
            process_graphs = []
            links = []
            for record_id, record in Persistence.items(Persistence.ET_PROCESS_GRAPHS):
                process_graphs.append({
                    "id": record_id,
                    "title": record.get("title", None),
                    "description": record.get("description", None),
                })
                links.append({
                    "href": "{}/process_graphs/{}".format(URL_ROOT, record_id),
                    "title": record.get("title", None),
                })
            return {
                "process_graphs": process_graphs,
                "links": links,
            }, 200
        else:
            process_graph = Persistence.get_by_id(Persistence.ET_PROCESS_GRAPHS,process_graph_id)
            process_graph["id"] = process_graph_id
            return process_graph, 200

    elif flask.request.method == 'POST':
        data = flask.request.get_json()

        process_graph_schema = PostProcessGraphsSchema()
        errors = process_graph_schema.validate(data)

        if errors:
            # Response procedure for validation will depend on how openeo_pg_parser_python will work
            return flask.make_response('Invalid request', 400)

        record_id = Persistence.create(Persistence.ET_PROCESS_GRAPHS, data)

        # add requested headers to 201 response:
        response = flask.make_response('', 201)
        response.headers['Location'] = '/process_graphs/{}'.format(record_id)
        response.headers['OpenEO-Identifier'] = record_id
        return response

    elif flask.request.method == 'DELETE':
        Persistence.delete(Persistence.ET_PROCESS_GRAPHS,process_graph_id)
        return flask.make_response('The process graph has been successfully deleted.', 204)

    elif flask.request.method == 'PATCH':
        data = flask.request.get_json()

        process_graph_schema = PostProcessGraphsSchema()
        errors = process_graph_schema.validate(data)

        if errors:
            # Response procedure for validation will depend on how openeo_pg_parser_python will work
            return flask.make_response('Invalid request', 400)

        Persistence.replace(Persistence.ET_PROCESS_GRAPHS,process_graph_id,data)
        return flask.make_response('The process graph data has been updated successfully.', 204)



@app.route('/result', methods=['POST'])
def api_result():
    if flask.request.method == 'POST':
        data = flask.request.get_json()

        schema = PostResultSchema()
        errors = schema.validate(data)

        if errors:
            log(WARN, "Invalid request: {}".format(errors))
            return flask.make_response('Invalid request: {}'.format(errors), 400)

        # !!! for now we simply always request some dummy data from SH and return it:
        url = 'https://services.sentinel-hub.com/ogc/wms/cd280189-7c51-45a6-ab05-f96a76067710?service=WMS&request=GetMap&layers=1_TRUE_COLOR&styles=&format=image%2Fpng&transparent=true&version=1.1.1&showlogo=false&name=Sentinel-2%20L1C&width=512&height=512&pane=activeLayer&maxcc=100&evalscriptoverrides=&time=2017-01-01%2F2017-02-01&srs=EPSG%3A4326&bbox=16.1,47.2,16.6,48.6'
        r = requests.get(url)
        r.raise_for_status()

        # pass the result back directly:
        response = flask.make_response(r.content, 200)
        response.headers['Content-Type'] = r.headers['Content-Type']
        return response


@app.route('/jobs', methods=['GET','POST'])
def api_jobs():
    if flask.request.method == 'GET':
        jobs = []
        links = []

        for record in Persistence.items(Persistence.ET_JOBS):
            jobs.append({
                "id": record["id"],
                "title": record.get("title", None),
                "description": record.get("description", None),
            })
            links.append({
                "href": "{}/jobs/{}".format(URL_ROOT, record.get("id")),
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

        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        data["current_status"] = "submitted"
        data["submitted"] = timestamp
        data["last_updated"] = timestamp
        data["should_be_cancelled"] = False

        record_id = Persistence.create(Persistence.ET_JOBS, data)

        # add requested headers to 201 response:
        response = flask.make_response('', 201)
        response.headers['Location'] = '/jobs/{}'.format(record_id)
        response.headers['OpenEO-Identifier'] = record_id
        return response


@app.route('/jobs/<job_id>', methods=['GET','PATCH','DELETE'])
def api_batch_job(job_id):
    if flask.request.method == 'GET':
        job = Persistence.get_by_id(Persistence.ET_JOBS, job_id)
        if job is None:
            return flask.make_response(jsonify(
                id = job_id,
                code = 404,
                message = "Batch job doesn't exist.",
                links = []
                ), 404)


        return flask.make_response(jsonify(
            id = job_id,
            title = job["title"],
            description = job["description"],
            process_graph = json.loads(job["process_graph"]),
            status = job["current_status"],  # "status" is reserved word in DynamoDB
            error = job["error_msg"],
            results = job["results"],
            submitted = job["submitted"],
            ), 200)

    elif flask.request.method == 'PATCH':
        current_job = Persistence.get_by_id(Persistence.ET_JOBS,job_id)

        if current_job["current_status"] in ["queued","running"]:
            return flask.make_response(jsonify(
                id = job_id,
                code = 400,
                message = 'openEO error: JobLocked',
                links = []
                ), 400)

        data = flask.request.get_json()

        process_graph_schema = PostJobsSchema()
        errors = process_graph_schema.validate(data)

        if errors:
            # Response procedure for validation will depend on how openeo_pg_parser_python will work
            return flask.make_response('Invalid request', 400)


        for key in data:
            Persistence.update_key(Persistence.ET_JOBS,job_id,key,data[key])

        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        Persistence.update_key(Persistence.ET_JOBS, job_id, "last_updated", timestamp)
        Persistence.update_key(Persistence.ET_JOBS, job_id, "current_status", "submitted")

        return flask.make_response('Changes to the job applied successfully.', 204)

    elif flask.request.method == 'DELETE':
        Persistence.delete(Persistence.ET_JOBS,job_id)
        return flask.make_response('The job has been successfully deleted.', 204)


@app.route('/jobs/<job_id>/results', methods=['POST','GET','DELETE'])
def add_job_to_queue(job_id):
    if flask.request.method == "POST":
        job = Persistence.get_by_id(Persistence.ET_JOBS,job_id)

        if job["current_status"] in ["submitted","finished","canceled","error"]:
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            Persistence.update_key(Persistence.ET_JOBS, job_id, "last_updated", timestamp)
            Persistence.update_key(Persistence.ET_JOBS, job_id, "current_status", "queued")

            return flask.make_response('The creation of the resource has been queued successfully.', 202)
        else:
            return flask.make_response(jsonify(
                id = job_id,
                code = 400,
                message = 'Job already queued or running.',
                links = []
                ), 400)

    elif flask.request.method == "GET":
        job = Persistence.get_by_id(Persistence.ET_JOBS,job_id)

        if job["current_status"] not in ["finished","error"]:
            return flask.make_response(jsonify(
                id = job_id,
                code = 503,
                message = 'openEO error: JobNotFinished',
                links = []
                ), 503)

        if job["current_status"] == "error":
            return flask.make_response(jsonify(
                id = job_id,
                code = 424,
                message = job["error_msg"],
                links = []
                ), 424)

        s3 = boto3.client('s3')
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
                title = job["title"],
                description = job["description"],
                updated = job["last_updated"],  # "updated" is a reserved word in DynamoDB
                links = links,
            ), 200)

    elif flask.request.method == "DELETE":
        job = Persistence.get_by_id(Persistence.ET_JOBS,job_id)

        if job["current_status"] in ["queued","running"]:
            Persistence.update_key(Persistence.ET_JOBS, job_id, "should_be_cancelled", True)
            return flask.make_response('Processing the job has been successfully canceled.', 200)

        return flask.make_response(jsonify(
            id = job_id,
            code = 400,
            message = 'Job is not queued or running.',
            links = []
            ), 400)



@app.route('/validation', methods=["GET"])
def validate_process_graph():
    data = flask.request.get_json()

    process_graph_schema = PGValidationSchema()
    errors = process_graph_schema.validate(data)

    return {
        "errors": errors,
    }, 200

if __name__ == '__main__':
    app.run()
