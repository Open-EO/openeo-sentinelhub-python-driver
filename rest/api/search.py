from .api_setup import *

from openeoerrors import ArgumentUnsupported
from processing.tpdi import TPDI

app_search = Blueprint("queryables", __name__)


@app_search.route("/search", methods=["GET"])
def get_common_queryables():
    collections = request.args.get("collections")
    bbox = request.args.get("bbox")
    intersects = request.args.get("intersects")
    datetime = request.args.get("datetime")
    limit = request.args.get("limit")

    if request.args.get("ids") is not None:
        raise ArgumentUnsupported("ids")

    return None, 200
