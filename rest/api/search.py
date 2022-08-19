from .api_setup import *

from processing.processing import search_tpdi_products
from processing.const import CommercialDataCollections

app_search = Blueprint("search", __name__)


@app_search.route("/search", methods=["GET"])
@authentication_provider.with_bearer_auth
def get_common_queryables():
    collections = request.args.get("collections")
    if collections is not None:
        collections = collections.split(",")

    bbox = request.args.get("bbox")
    if bbox is not None:
        bbox = list(map(float, bbox.split(",")))

    intersects = request.args.get("intersects", type=dict)
    datetime = request.args.get("datetime")
    limit = request.args.get("limit", type=int)

    if request.args.get("ids") is not None:
        raise BadRequest("Argument 'ids' is not supported.")

    if len(collections) != 1:
        raise BadRequest("Argument 'collections' must be an array of length 1.")

    if not CommercialDataCollections.is_commercial(collections[0]):
        raise BadRequest("Search only supported for commercial data collections.")

    search_results = search_tpdi_products(
        collection_id=collections[0], bbox=bbox, intersects=intersects, datetime=datetime, limit=limit
    )

    return search_results, 200
