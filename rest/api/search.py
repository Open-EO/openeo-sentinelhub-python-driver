from .api_setup import *

from processing.processing import search_tpdi_products
from processing.const import CommercialDataCollections
from schemas import PostSearchSchema

app_search = Blueprint("search", __name__)


@app_search.route("/search", methods=["GET", "POST"])
@authentication_provider.with_bearer_auth
def search_available_items():
    if flask.request.method == "GET":
        collections = request.args.get("collections")
        if collections is not None:
            collections = collections.split(",")

        bbox = request.args.get("bbox")
        if bbox is not None:
            bbox = list(map(float, bbox.split(",")))

        if request.args.get("filter"):
            raise BadRequest("Argument 'filter' is not supported by GET /search. Please use POST /search instead.")

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

    if flask.request.method == "POST":
        data = flask.request.get_json()

        search_schema = PostSearchSchema()
        errors = search_schema.validate(data)

        if errors:
            raise BadRequest(f"Payload schema not valid: {errors}")

        collections = data["collections"]

        if data.get("ids") is not None:
            raise BadRequest("Argument 'ids' is not supported.")

        if len(collections) != 1:
            raise BadRequest("Argument 'collections' must be an array of length 1.")

        if not CommercialDataCollections.is_commercial(collections[0]):
            raise BadRequest("Search only supported for commercial data collections.")

        search_results = search_tpdi_products(
            collection_id=collections[0],
            bbox=data["bbox"],
            intersects=data.get("intersects"),
            datetime=data["datetime"],
            filter_query=data.get("filter"),
            limit=data.get("limit"),
        )

        return search_results, 200
