from flask import Flask, url_for


app = Flask(__name__)


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


if __name__ == '__main__':
    app.run()
