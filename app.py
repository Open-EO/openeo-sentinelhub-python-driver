import flask
from flask import Flask, url_for, jsonify
from flask_marshmallow import Marshmallow
import os
from schemas import PostProcessGraphsSchema, PostJobsSchema, PostResultSchema, PGValidationSchema
import datetime
import requests
from logging import log, INFO, WARN

from dynamodb import Persistence


app = Flask(__name__)
app.url_map.strict_slashes = False


URL_ROOT = os.environ.get('URL_ROOT', '').rstrip('/')


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
    omitted_urls = ["/static/<path:filename>","/create_tables"]

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
            for record_id, record in Persistence.items("process_graphs"):
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

@app.route('/jobs', methods=['GET','POST'])
def api_jobs():
    if flask.request.method == 'GET':
        jobs = []
        links = []

        for record_id, record in Persistence.items("jobs"):
            jobs.append({
                "id": record_id,
                "title": record.get("title", None),
                "description": record.get("description", None),
            })
            links.append({
                "href": "{}/jobs/{}".format(URL_ROOT, record_id),
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
            return flask.make_response('Invalid request', 400)

        data["status"] = "submitted"
        data["submitted"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        record_id = Persistence.create(Persistence.ET_JOBS, data)

        # add requested headers to 201 response:
        response = flask.make_response('', 201)
        response.headers['Location'] = '/process_graphs/{}'.format(record_id)
        response.headers['OpenEO-Identifier'] = record_id
        return response


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


@app.route('/jobs/<job_id>', methods=['GET','PATCH','DELETE'])
def api_batch_job(job_id):
    if flask.request.method == 'GET':
        job = Persistence.get_by_id(Persistence.ET_JOBS, job_id)
        job["id"] = job_id
        return job, 200

    elif flask.request.method == 'PATCH':
        data = flask.request.get_json()

        process_graph_schema = PostJobsSchema()
        errors = process_graph_schema.validate(data)

        if errors:
            # Response procedure for validation will depend on how openeo_pg_parser_python will work
            return flask.make_response('Invalid request', 400)

        data["updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        Persistence.replace(Persistence.ET_JOBS,job_id,data)
        return flask.make_response('Changes to the job applied successfully.', 204)

    elif flask.request.method == 'DELETE':
        Persistence.delete(Persistence.ET_JOBS,job_id)
        return flask.make_response('The job has been successfully deleted.', 204)



@app.route('/validation', methods=["GET"])
def validate_process_graph():
    data = flask.request.get_json()

    process_graph_schema = PGValidationSchema()
    errors = process_graph_schema.validate(data)

    return {
        "errors": errors,
    }, 200

@app.route('/create_tables', methods=['GET'])
def create_dynamoby_tables():
    Persistence.ensure_table_exists(Persistence.ET_PROCESS_GRAPHS)
    Persistence.ensure_table_exists(Persistence.ET_JOBS)
    return {}, 200

if __name__ == '__main__':
    app.run()

