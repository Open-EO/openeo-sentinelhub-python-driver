from .api_setup import *

from schemas import PostOrdersSchema
from processing.tpdi import TPDI
from processing.processing import create_tpdi_order

app_orders = Blueprint("app_orders", __name__)


@app_orders.route("/orders", methods=["GET", "POST"])
@authentication_provider.with_bearer_auth
def commercial_data_orders():
    if flask.request.method == "GET":
        pass

    elif flask.request.method == "POST":
        data = flask.request.get_json()

        payload_schema = PostOrdersSchema()
        errors = payload_schema.validate(data)

        if errors:
            raise BadRequest(str(errors))

        order = create_tpdi_order(data["collection_id"], data["bounds"], data["products"], data["parameters"])
        response = flask.make_response("", 201)
        response.headers["Location"] = "/orders/{}".format(order["id"])
        response.headers["OpenEO-Identifier"] = order["id"]
        return response


@app_orders.route("/orders/<order_id>", methods=["GET", "POST", "DELETE"])
@authentication_provider.with_bearer_auth
def commercial_data_order(order_id):
    if flask.request.method == "GET":
        pass

    elif flask.request.method == "POST":
        pass

    elif flask.request.method == "DELETE":
        pass
