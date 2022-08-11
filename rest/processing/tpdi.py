from functools import wraps
from requests import HTTPError

import requests

from .const import OpenEOOrderStatus
from openeoerrors import OrderNotFound


class TPDI:
    def __init__(self, collection_id=None, access_token=None):
        self.access_token = access_token
        self.auth_headers = {"Authorization": f"Bearer {self.access_token}"}

        if collection_id is not None:
            class_types_for_collectionId = {
                "PLEIADES": TPDIPleiades,
                "SPOT": TPDISPOT,
                "PLANETSCOPE": TPDITPLanetscope,
                "WORLDVIEW": TPDITMaxar,
            }
            self.__class__ = class_types_for_collectionId[collection_id]

    def with_error_handling(func):
        @wraps(func)
        def decorated_function(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except HTTPError as err:
                if err.response.status_code == 404:
                    raise OrderNotFound
                raise Exception(
                    f"HTTP {err.response.status_code}: {err.response.reason}. Response: {err.response.text}"
                )

        return decorated_function

    @with_error_handling
    def create_order(self, geometry, products, parameters):
        payload = self.generate_payload(geometry, products, parameters)
        r = requests.post(
            "https://services.sentinel-hub.com/api/v1/dataimport/orders",
            json=payload,
            headers=self.auth_headers,
        )
        r.raise_for_status()
        return r.json()

    @with_error_handling
    def get_all_orders(self):
        r = requests.get("https://services.sentinel-hub.com/api/v1/dataimport/orders", headers=self.auth_headers)
        r.raise_for_status()
        data = r.json()
        return self.convert_orders_to_openeo_format(data["data"]), data["links"]

    @with_error_handling
    def get_order(self, order_id):
        r = requests.get(
            f"https://services.sentinel-hub.com/api/v1/dataimport/orders/{order_id}", headers=self.auth_headers
        )
        r.raise_for_status()
        order = r.json()
        return self.convert_order_to_openeo_format(order)

    @with_error_handling
    def delete_order(self, order_id):
        r = requests.delete(
            f"https://services.sentinel-hub.com/api/v1/dataimport/orders/{order_id}", headers=self.auth_headers
        )
        r.raise_for_status()

    def generate_payload(self, geometry, products, parameters):
        payload = {
            "input": {
                "provider": self.provider,
                "bounds": {"geometry": geometry},
                "data": [self.get_payload_data(products, parameters)],
            }
        }
        return payload

    def get_payload_data(self, parameters):
        raise NotImplementedError

    def convert_orders_to_openeo_format(self, orders_sh):
        orders = []
        for order in orders_sh:
            orders.append(self.convert_order_to_openeo_format(order))
        return orders

    def convert_order_to_openeo_format(self, order):
        return {
            "order:id": order["id"],
            "order:status": OpenEOOrderStatus.from_sentinelhub_order_status(order["status"]).value,
            "order:date": order["created"],
        }


class TPDIAirbus(TPDI):
    provider = "AIRBUS"

    def get_payload_data(self, products, parameters):
        return {"constellation": self.constellation, "products": [{"id": product} for product in products]}


class TPDIPleiades(TPDIAirbus):
    constellation = "PHR"


class TPDISPOT(TPDIAirbus):
    constellation = "SPOT"


class TPDITPLanetscope(TPDI):
    provider = "PLANET"

    def generate_payload(self, geometry, products, parameters):
        payload = super().generate_payload(geometry, products, parameters)
        payload["input"]["planetApiKey"] = planetApiKey

    def get_payload_data(self, products, parameters):
        return {
            "itemType": parameters["item_type"],
            "productBundle": parameters["product_bundle"],
            "harmonizeTo": parameters["harmonize_to"],
            "itemIds": products,
        }


class TPDITMaxar(TPDI):
    provider = "MAXAR"

    def get_payload_data(self, products, parameters):
        return {"productBands": "4BB", "selectedImages": products}
