from functools import wraps
from requests import HTTPError

import requests
from sentinelhub.time_utils import parse_time_interval

from processing.const import OpenEOOrderStatus, CommercialDataCollections
from openeoerrors import OrderNotFound, BadRequest


class TPDI:
    def __init__(self, collection_id=None, access_token=None):
        self.collection_id = collection_id
        self.access_token = access_token
        self.auth_headers = {"Authorization": f"Bearer {self.access_token}"}

        self.class_types_for_collection_id = {
            "PLEIADES": TPDIPleiades,
            "SPOT": TPDISPOT,
            "PLANETSCOPE": TPDITPLanetscope,
            "WORLDVIEW": TPDITMaxar,
        }

        if collection_id is not None:
            self.__class__ = self.class_types_for_collection_id[collection_id]

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
    def create_order(self, geometry, items, parameters):
        payload = self.generate_payload(geometry, items, parameters)
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

    @with_error_handling
    def confirm_order(self, order_id):
        r = requests.post(
            f"https://services.sentinel-hub.com/api/v1/dataimport/orders/{order_id}/confirm", headers=self.auth_headers
        )
        r.raise_for_status()
        return r

    @with_error_handling
    def search(self, bbox, intersects, datetime, filter_query, limit):
        filter_query = self.parse_filter_query(filter_query)
        payload = self.generate_search_payload_from_params(
            bbox=bbox, intersects=intersects, datetime=datetime, filter_query=filter_query
        )

        r = requests.post(
            "https://services.sentinel-hub.com/api/v1/dataimport/search", json=payload, headers=self.auth_headers
        )
        r.raise_for_status()
        return self.convert_search_results(r.json())

    def generate_search_payload_from_params(self, bbox, datetime, intersects=None, filter_query=None):
        return {
            "provider": self.provider,
            "bounds": self.get_payload_bounds(bbox, intersects),
            "data": [{"dataFilter": self.get_data_filter(datetime, filter_query)}],
        }

    def get_data_filter(self, datetime, filter_query):
        return {"timeRange": self.get_timerange_object_from_datetime(datetime)}

    def get_timerange_object_from_datetime(self, datetime):
        datetime = datetime.split("/")
        if len(datetime) == 1:
            datetime = datetime[0]
        from_time, to_time = parse_time_interval(datetime)
        return {"from": from_time.isoformat(), "to": to_time.isoformat()}

    def get_payload_bounds(self, bbox, geometry):
        bounds = {}
        if bbox is not None:
            bounds["bbox"] = bbox
        if geometry is not None:
            bounds["geometry"] = geometry
        return bounds

    def convert_search_results(self, search_results):
        return {
            "type": "FeatureCollection",
            "features": [self.align_result_with_STAC(result) for result in search_results["features"]],
            "links": [],
        }

    def align_result_with_STAC(self, result):
        raise NotImplementedError

    def parse_filter_query(self, filter_query, filter_parameters=dict()):
        """
        Accepts cql2-json and returns a dictionary of parameters-value pairs.
        We can only support "and" and "=" operations.
        """
        if filter_query is None:
            return None

        operation = filter_query["op"]

        if operation == "and":
            for argument in filter_query["args"]:
                self.parse_filter_query(argument, filter_parameters=filter_parameters)
        elif operation == "=":
            parameter_name = filter_query["args"][0]["property"]
            parameter_value = filter_query["args"][1]
            filter_parameters[parameter_name] = parameter_value
        else:
            raise BadRequest(f"Filter operation '{operation}' not supported.")

        return filter_parameters

    def add_filter_value_to_data_filter(self, parameter_name, filter_query_params, data_filter):
        if parameter_name in filter_query_params:
            data_filter[parameter_name] = filter_query_params[parameter_name]
        return data_filter

    def generate_payload(self, geometry, items, parameters):
        payload = {
            "input": {
                "provider": self.provider,
                "bounds": {"geometry": geometry},
                "data": [self.get_payload_data(items, parameters)],
            }
        }
        return payload

    def get_payload_data(self, parameters):
        raise NotImplementedError

    @staticmethod
    def get_items_list_from_order(order):
        raise NotImplementedError

    def convert_orders_to_openeo_format(self, orders_sh):
        orders = []
        for order in orders_sh:
            orders.append(self.convert_order_to_openeo_format(order))
        return orders

    def convert_order_to_openeo_format(self, order):
        collection_id = self.get_collection_id_from_order(order).value
        tpdi_class = self.class_types_for_collection_id[collection_id]
        return {
            "id": order["id"],
            "order:id": order["id"],
            "order:status": OpenEOOrderStatus.from_sentinelhub_order_status(order["status"]).value,
            "order:date": order["created"],
            "source_collection_id": collection_id,
            "target_collection_id": collection_id,  # Currently hardcoded to have the same source and target collection
            "items": tpdi_class.get_items_list_from_order(order),
            "costs": None,
        }

    def get_collection_id_from_order(self, order):
        collection = order["input"]["provider"]
        constellation = order["input"]["data"][0].get("constellation")
        return CommercialDataCollections.from_sentinelhub_provider(collection, constellation)


class TPDIAirbus(TPDI):
    provider = "AIRBUS"

    def get_payload_data(self, items, parameters):
        return {"constellation": self.constellation, "products": [{"id": item} for item in items]}

    def generate_search_payload_from_params(self, bbox, datetime, intersects=None, filter_query=None):
        payload = super().generate_search_payload_from_params(
            bbox=bbox, intersects=intersects, datetime=datetime, filter_query=filter_query
        )
        payload["data"][0]["constellation"] = self.constellation
        return payload

    def get_data_filter(self, datetime, filter_query):
        data_filter = super().get_data_filter(datetime, filter_query)
        self.add_filter_value_to_data_filter("maxCloudCoverage", filter_query, data_filter)
        self.add_filter_value_to_data_filter("processingLevel", filter_query, data_filter)
        self.add_filter_value_to_data_filter("maxSnowCoverage", filter_query, data_filter)
        self.add_filter_value_to_data_filter("maxIncidenceAngle", filter_query, data_filter)

        if "expirationDate" in filter_query:
            data_filter["expirationDate"] = self.get_timerange_object_from_datetime(filter_query["expirationDate"])

        return data_filter

    @staticmethod
    def get_items_list_from_order(order):
        return [item["id"] for item in order["input"]["data"][0]["products"]]

    def align_result_with_STAC(self, result):
        return {
            "type": "Feature",
            "stac_version": "1.0.0",
            "id": result["properties"]["id"],
            "geometry": result["geometry"],
            "properties": result["properties"],
            "links": [],
            "assets": {},
        }


class TPDIPleiades(TPDIAirbus):
    constellation = "PHR"


class TPDISPOT(TPDIAirbus):
    constellation = "SPOT"


class TPDITPLanetscope(TPDI):
    provider = "PLANET"

    def generate_payload(self, geometry, items, parameters):
        payload = super().generate_payload(geometry, items, parameters)
        payload["input"]["planetApiKey"] = planetApiKey
        return payload

    def get_payload_data(self, items, parameters):
        return {
            "itemType": parameters["item_type"],
            "productBundle": parameters["product_bundle"],
            "harmonizeTo": parameters["harmonize_to"],
            "itemIds": items,
        }

    def generate_search_payload_from_params(self, bbox, datetime, intersects=None, filter_query=None):
        payload = super().generate_search_payload_from_params(
            bbox=bbox, intersects=intersects, datetime=datetime, filter_query=filter_query
        )
        payload["planetApiKey"] = planetApiKey
        payload["itemType"] = filter_query["itemType"]
        payload["productBundle"] = filter_query["productBundle"]
        return payload

    @staticmethod
    def get_items_list_from_order(order):
        return order["input"]["data"][0]["itemIds"]

    def get_data_filter(self, datetime, filter_query):
        data_filter = super().get_data_filter(datetime, filter_query)
        self.add_filter_value_to_data_filter("maxCloudCoverage", filter_query, data_filter)
        return data_filter


class TPDITMaxar(TPDI):
    provider = "MAXAR"

    def get_payload_data(self, items, parameters):
        return {"productBands": "4BB", "selectedImages": items}

    def generate_search_payload_from_params(self, bbox, datetime, intersects=None, filter_query=None):
        payload = super().generate_search_payload_from_params(
            bbox=bbox, intersects=intersects, datetime=datetime, filter_query=filter_query
        )
        payload["data"][0]["productBands"] = "4BB"
        return payload

    @staticmethod
    def get_items_list_from_order(order):
        return order["input"]["data"][0]["selectedImages"]

    def align_result_with_STAC(self, result):
        return {
            "type": "Feature",
            "stac_version": "1.0.0",
            "id": result["catalogID"],
            "geometry": result["geometry"],
            "properties": result,
            "links": [],
            "assets": {},
        }

    def get_data_filter(self, datetime, filter_query):
        data_filter = super().get_data_filter(datetime, filter_query)
        self.add_filter_value_to_data_filter("maxCloudCoverage", filter_query, data_filter)
        self.add_filter_value_to_data_filter("minOffNadir", filter_query, data_filter)
        self.add_filter_value_to_data_filter("maxOffNadir", filter_query, data_filter)
        self.add_filter_value_to_data_filter("minSunElevation", filter_query, data_filter)
        self.add_filter_value_to_data_filter("maxSunElevation", filter_query, data_filter)
        self.add_filter_value_to_data_filter("sensor", filter_query, data_filter)
        return data_filter
