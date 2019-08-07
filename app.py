import flask
from flask import Flask, url_for, jsonify
from flask_marshmallow import Marshmallow
import os
from udf import execute_udf
from schemas import ProcessGraphsRequest


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
        Returns a list of endpoints (url and allowed methods). Endpoints which
        require parameters are not filtered out because openEO documentation includes them.
    """
    endpoints = []

    for rule in app.url_map.iter_rules():
        url = rule.rule
        endpoints.append({
            "path": url,
            "methods": list(rule.methods - set(["OPTIONS", "HEAD"])),
        })
    return endpoints

@app.route('/process_graphs', methods=["GET","POST"])
@app.route('/process_graphs/<process_graph_id>', methods=["GET", "DELETE", "PATCH"])
def api_process_graphs(process_graph_id=None):
    if flask.request.method in ['GET', 'HEAD']:
        if process_graph_id is None:
            print(process_graph_id)
            process_graphs = []
            links = []
            for record_id, record in Persistence.items("process_graphs"):
                print("RECORD:",record);
                continue
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
            process_graph = Persistence.get_graph_by_id(Persistence.ET_PROCESS_GRAPHS,process_graph_id)
            return {
                "title": None,
                "description": None,
                "process_graph": process_graph
            }, 200

    elif flask.request.method == 'POST':
        # !!! input validation is missing!
        # print(flask.request.form)
        data = flask.request.form
        print("Data:",data)
        if data is None: return flask.make_response('Empty request', 404)
        record_id = Persistence.create(Persistence.ET_PROCESS_GRAPHS, data)

        # add requested headers to 201 response:
        response = flask.make_response('', 201)
        response.headers['Location'] = '/process_graphs/{}'.format(record_id)
        response.headers['OpenEO-Identifier'] = record_id
        return response

    elif flask.request.method == 'DELETE':
        print("DELETING!!!\n")
        # print(flask.request.data)
        Persistence.delete(Persistence.ET_PROCESS_GRAPHS,process_graph_id)
        return flask.make_response('The process graph has been successfully deleted.', 204)

    elif flask.request.method == 'PATCH':
        print("PATCHING!\n")
        data = flask.request.form
        Persistence.replace_graph(Persistence.ET_PROCESS_GRAPHS,process_graph_id,data)
        return flask.make_response('The process graph data has been updated successfully.', 204)

@app.route('/jobs', methods=['GET','POST'])
def api_jobs():
    if flask.request.method == 'GET':
        process_graphs = []
        links = []

        for record_id, record in Persistence.items("jobs"):
            print("RECORD:",record);
            continue
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
        data = flask.request.form
        print("Data:",data)
        if data is None: return flask.make_response('Empty request', 404)

        record_id = Persistence.create(Persistence.ET_JOBS, data)

        # add requested headers to 201 response:
        response = flask.make_response('', 201)
        response.headers['Location'] = '/process_graphs/{}'.format(record_id)
        response.headers['OpenEO-Identifier'] = record_id
        return response

@app.route('/jobs/<job_id>', methods=['GET','POST','PATCH','DELETE'])
def batch_job(job_id):
    if flask.request.method == 'GET':
        pass

    elif flask.request.method == 'POST':
        pass

    elif flask.request.method == 'PATCH':
        pass

    elif flask.request.method == 'DELETE':
        pass
 

@app.route('/jobs/<job_id>/results', methods=['POST'])
def process_batch_job(job_id):
    data = {'udf':'import sys\nfor i in range(5):\n\tprint(i)\na = sys.argv[1]\nreturn "script executed with arg %s" % a'}
    result = execute_udf(data)


@app.route("/test", methods=["GET","POST"])
def test():
    print("Test json schema and graph validation")
    process_graph_schema = ProcessGraphsRequest()
    print(flask.request.get_json())
    result = process_graph_schema.validate(flask.request.get_json())
    print(result)
    return flask.make_response(result, 201)

if __name__ == '__main__':
    app.run()

