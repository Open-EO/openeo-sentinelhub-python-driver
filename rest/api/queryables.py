from .api_setup import *

from schemas import PostOrdersSchema
from processing.tpdi import TPDI
from processing.processing import (
    create_tpdi_order,
    get_all_tpdi_orders,
    get_tpdi_order,
    delete_tpdi_order,
    confirm_tpdi_order,
)

app_queryables = Blueprint("queryables", __name__)

commercial_collections_queryables = {
    "PLANETSCOPE": {
        "timeRange": {
            "type": "object",
            "properties": {
                "from": {
                    "type": "string",
                    "description": "ISO-8601 time representing start of search interval, e.g. 2019-01-31T14:00:00+01:00",
                    "format": "date-time",
                },
                "to": {
                    "type": "string",
                    "description": "ISO-8601 time representing end of search interval, e.g. 2019-02-05T15:00:00+01:00.",
                    "format": "date-time",
                },
            },
        },
        "maxCloudCoverage": {
            "description": "The maximum allowable cloud coverage in percent.",
            "type": "number",
            "format": "double",
            "minimum": 0,
            "maximum": 100,
            "default": 100,
        },
        "productBundle": {
            "type": "string",
            "enum": [
                "analytic_udm2",
                "analytic_sr_udm2",
                "analytic_8b_udm2",
                "analytic_8b_sr_udm2",
                "analytic",
                "analytic_sr",
                "panchromatic",
            ],
            "description": 'When ordering, selects the product bundle (that is, the group of assets) to order.\n\nWhen searching, limits search to products available as the specified product bundle.\nOptionally it can be omitted when searching for the `PSScene4Band` item type,\nin which case the search will return all products available as any of the product bundles.\n\nSupported values depend on item type:\n* for `PSScene`, the product bundles containing "*udm2*" are supported,\n* for `PSScene4Band`, the analytic product bundles **not** containing "*8b*" are supported.\n* for `SkySatScene`, `analytic_udm2`, `analytic_sr_udm2` and `panchromatic` are supported.\n\nOther values used by Planet but not listed here are not supported.\n',
        },
        "itemType": {
            "type": "string",
            "enum": ["PSScene", "SkySatScene"],
            "description": "The item type of data to search for or order:\n* Use [PSScene](https://developers.planet.com/docs/data/psscene/) to order PlanetScope\ndata unless you plan to import the data into an existing BYOC collection that contains\n[PSScene4Band](https://developers.planet.com/docs/data/psscene4band/) data. Use [SkySatScene](https://developers.planet.com/docs/data/skysatscene/) to order SkySat data.\n",
        },
    },
    "PLEIADES": {
        "timeRange": {
            "type": "object",
            "properties": {
                "from": {
                    "type": "string",
                    "description": "ISO-8601 time representing start of search interval, e.g. 2019-01-31T14:00:00+01:00",
                    "format": "date-time",
                },
                "to": {
                    "type": "string",
                    "description": "ISO-8601 time representing end of search interval, e.g. 2019-02-05T15:00:00+01:00.",
                    "format": "date-time",
                },
            },
        },
        "maxCloudCoverage": {
            "description": "The maximum allowable cloud coverage in percent.",
            "type": "number",
            "format": "double",
            "minimum": 0,
            "maximum": 100,
            "default": 100,
        },
        "processingLevel": {
            "type": "string",
            "description": "When searching, you will receive results from the full catalog as well as the Living Library, which holds images that have cloud cover under 30% and Incidence angle under 40°. If you want to search only Living Library results, you will need to filter using processingLevel. This value could be equal to SENSOR (images which meet Living Library criteria) and ALBUM (images that do not meeting Living Library criteria in terms of incidence angle and cloud cover).\n",
            "enum": ["SENSOR", "ALBUM"],
        },
        "maxSnowCoverage": {
            "description": "The maximum allowable snow coverage in percent.",
            "type": "number",
            "format": "double",
            "minimum": 0,
            "maximum": 100,
            "default": 100,
        },
        "maxIncidenceAngle": {
            "description": "The maximum allowable incidence angle in degrees.",
            "type": "number",
            "format": "double",
            "minimum": 0,
            "maximum": 90,
            "default": 90,
        },
        "expirationDate": {
            "type": "object",
            "properties": {
                "from": {
                    "type": "string",
                    "description": "ISO-8601 time representing start of search interval, e.g. 2019-01-31T14:00:00+01:00",
                    "format": "date-time",
                },
                "to": {
                    "type": "string",
                    "description": "ISO-8601 time representing end of search interval, e.g. 2019-02-05T15:00:00+01:00.",
                    "format": "date-time",
                },
            },
        },
    },
    "SPOT": {
        "timeRange": {
            "type": "object",
            "properties": {
                "from": {
                    "type": "string",
                    "description": "ISO-8601 time representing start of search interval, e.g. 2019-01-31T14:00:00+01:00",
                    "format": "date-time",
                },
                "to": {
                    "type": "string",
                    "description": "ISO-8601 time representing end of search interval, e.g. 2019-02-05T15:00:00+01:00.",
                    "format": "date-time",
                },
            },
        },
        "maxCloudCoverage": {
            "description": "The maximum allowable cloud coverage in percent.",
            "type": "number",
            "format": "double",
            "minimum": 0,
            "maximum": 100,
            "default": 100,
        },
        "processingLevel": {
            "type": "string",
            "description": "When searching, you will receive results from the full catalog as well as the Living Library, which holds images that have cloud cover under 30% and Incidence angle under 40°. If you want to search only Living Library results, you will need to filter using processingLevel. This value could be equal to SENSOR (images which meet Living Library criteria) and ALBUM (images that do not meeting Living Library criteria in terms of incidence angle and cloud cover).\n",
            "enum": ["SENSOR", "ALBUM"],
        },
        "maxSnowCoverage": {
            "description": "The maximum allowable snow coverage in percent.",
            "type": "number",
            "format": "double",
            "minimum": 0,
            "maximum": 100,
            "default": 100,
        },
        "maxIncidenceAngle": {
            "description": "The maximum allowable incidence angle in degrees.",
            "type": "number",
            "format": "double",
            "minimum": 0,
            "maximum": 90,
            "default": 90,
        },
        "expirationDate": {
            "type": "object",
            "properties": {
                "from": {
                    "type": "string",
                    "description": "ISO-8601 time representing start of search interval, e.g. 2019-01-31T14:00:00+01:00",
                    "format": "date-time",
                },
                "to": {
                    "type": "string",
                    "description": "ISO-8601 time representing end of search interval, e.g. 2019-02-05T15:00:00+01:00.",
                    "format": "date-time",
                },
            },
        },
    },
    "WORLDVIEW": {
        "timeRange": {
            "type": "object",
            "properties": {
                "from": {
                    "type": "string",
                    "description": "ISO-8601 time representing start of search interval, e.g. 2019-01-31T14:00:00+01:00",
                    "format": "date-time",
                },
                "to": {
                    "type": "string",
                    "description": "ISO-8601 time representing end of search interval, e.g. 2019-02-05T15:00:00+01:00.",
                    "format": "date-time",
                },
            },
        },
        "maxCloudCoverage": {
            "description": "The maximum allowable cloud coverage in percent.",
            "type": "number",
            "format": "double",
            "minimum": 0,
            "maximum": 100,
            "default": 100,
        },
        "minOffNadir": {"type": "number", "format": "int", "minimum": 0, "maximum": 45, "default": 0},
        "maxOffNadir": {"type": "number", "format": "int", "minimum": 0, "maximum": 45, "default": 45},
        "minSunElevation": {
            "description": "The minimum allowable sun elevation in degrees",
            "type": "number",
            "format": "int",
            "minimum": 0,
            "maximum": 90,
            "default": 0,
        },
        "maxSunElevation": {
            "description": "The maximum allowable sun elevation in degrees",
            "type": "number",
            "format": "int",
            "minimum": 0,
            "maximum": 90,
            "default": 90,
        },
        "sensor": {
            "description": "If specified, limits search results to a single sensor (satellite).\nResults are also filtered to include only sensors that support the requested `productBands`. Thus, if a sensor that does not support all bands is specified, no results will be returned.\n",
            "type": "string",
            "enum": ["WV01", "WV02", "WV03", "WV04", "GE01"],
        },
    },
}


def QUERYABLES_TEMPLATE():
    return {
        "$schema": "https://json-schema.org/draft/2019-09/schema",
        "$id": "https://stac-api.example.com/queryables",
        "properties": {},
        "additionalProperties": True,
    }


@app_queryables.route("/queryables", methods=["GET"])
def get_common_queryables():
    return QUERYABLES_TEMPLATE(), 200


@app_queryables.route("/collections/<collection_id>/queryables", methods=["GET"])
def get_collection_queryables(collection_id):
    collection_queryables = QUERYABLES_TEMPLATE()
    collection_queryables["properties"] = commercial_collections_queryables.get(collection_id, {})
    return collection_queryables, 200
