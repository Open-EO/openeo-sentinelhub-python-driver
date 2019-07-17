import flask
from flask import Flask, url_for
import os


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
        require parameters are filtered out.
    """
    endpoints = []

    def requires_params(rule):
        defaults = rule.defaults if rule.defaults is not None else ()
        arguments = rule.arguments if rule.arguments is not None else ()
        return len(defaults) < len(arguments)

    for rule in app.url_map.iter_rules():
        if requires_params(rule):
            continue
        url = url_for(rule.endpoint, **(rule.defaults or {}))
        endpoints.append({
            "path": url,
            "methods": list(rule.methods - set(["OPTIONS", "HEAD"])),
        })
    return endpoints


@app.route('/process_graphs', methods=["GET", "POST"])
def api_process_graphs():
    if flask.request.method in ['GET', 'HEAD']:
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

    elif flask.request.method == 'POST':
        # !!! input validation is missing!
        data = flask.request.get_json()
        record_id = Persistence.create("process_graphs", data)

        # add requested headers to 201 response:
        response = flask.make_response('', 201)
        response.headers['Location'] = '/process_graphs/{}'.format(record_id)
        response.headers['OpenEO-Identifier'] = record_id
        return response


if __name__ == '__main__':
    app.run()
