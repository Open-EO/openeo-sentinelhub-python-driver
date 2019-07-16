from flask import Flask


app = Flask(__name__)


@app.route('/')
def api_root():
    return {
        "api_version": "0.4.1",
        "backend_version": "0.0.1",
        "title": "Sentinel Hub OpenEO",
        "description": "Sentinel Hub OpenEO by [Sinergise](https://sinergise.com)",
        "endpoints": get_endpoints(),
    }


def get_endpoints():
    return [
        {
            "path": "/",
            "methods": [
                "GET"
            ]
        },
    ]


if __name__ == '__main__':
    app.run()
