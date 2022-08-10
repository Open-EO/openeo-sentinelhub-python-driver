import requests


class TPDI:
    def __init__(self, collection_id, access_token=None):
        self.access_token = access_token
        class_types_for_collectionId = {
            "PLEIADES": TPDIPleiades,
            "SPOT": TPDISPOT,
            "PLANETSCOPE": TPDITPLanetscope,
            "WORLDVIEW": TPDITMaxar,
        }
        self.__class__ = class_types_for_collectionId[collection_id]

    def create_order(self, geometry, products, parameters):
        payload = self.generate_payload(geometry, products, parameters)
        r = requests.post(
            "https://services.sentinel-hub.com/api/v1/dataimport/orders",
            json=payload,
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        r.raise_for_status()
        return r.json()

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
