from openeoerrors import UnsupportedGeometry


def iterate(obj):
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            yield i, v
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v


def inject_variables_in_process_graph(pg_object, variables):
    """
    Injects variables into the object in place.
    """
    for key, value in iterate(pg_object):
        if isinstance(value, dict) and len(value) == 1 and "from_parameter" in value:
            if value["from_parameter"] in variables:
                pg_object[key] = variables[value["from_parameter"]]
        elif isinstance(value, dict) or isinstance(value, list):
            inject_variables_in_process_graph(value, variables)


def multi_polygon(geometries):
    """
    Converts FeatureCollection or Geometrycollection to MultiPolygon
    """
    coordinates = []
    for geometry in geometries:
        if is_polygon(geometry):
            coordinates.append(geometry["coordinates"])
        elif is_multi_polygon(geometry):
            for polygon in geometry["coordinates"]:
                coordinates.append(polygon)
    return {
        "type": "MultiPolygon",
        "coordinates": coordinates,
    }


def parse_geojson(geojson):
    """
    Converts FeatureCollection or Geometrycollection to MultiPolygon
    Returns Polygon or MultiPolygon if the input is of the same type
    """
    if not is_geojson(geojson):
        raise Exception("Argument is not a GeoJSON")
    elif is_polygon_or_multi_polygon(geojson):
        return geojson
    elif is_feature(geojson):
        if is_polygon_or_multi_polygon(geojson["geometry"]):
            return parse_geojson(geojson["geometry"])
    elif is_feature_collection(geojson):
        polygons = []
        for geometry in geojson["features"]:
            polygons.append(geometry["geometry"])
        return parse_geojson(multi_polygon(polygons))
    elif is_geometry_collection(geojson):
        polygons = []
        for geometry in geojson["geometries"]:
            polygons.append(geometry)
        return parse_geojson(multi_polygon(polygons))
    else:
        raise UnsupportedGeometry()


def validate_geojson(geojson):
    """
    Polygon or MultiPolygon geometry,
    Feature with a Polygon or MultiPolygon geometry,
    FeatureCollection containing Polygon or MultiPolygon geometries, or
    GeometryCollection containing Polygon or MultiPolygon geometries. To maximize interoperability, GeometryCollection should be avoided in favour of one of the alternatives above.
    """
    is_valid = (
        is_polygon_or_multi_polygon(geojson)
        or is_feature(geojson)
        or is_feature_collection(geojson)
        or is_geometry_collection(geojson)
    )
    if is_valid:
        return True
    else:
        raise UnsupportedGeometry()


def is_geojson(geojson):
    return (
        isinstance(geojson, dict)
        and "type" in geojson
        and geojson["type"]
        in (
            "Point",
            "MultiPoint",
            "LineString",
            "MultiLineString",
            "Polygon",
            "MultiPolygon",
            "Feature",
            "FeatureCollection",
            "GeometryCollection",
        )
    )


def is_polygon_or_multi_polygon(geometry):
    return is_polygon(geometry) or is_multi_polygon(geometry)


def is_polygon(geojson_geometry):
    return isinstance(geojson_geometry, dict) and "type" in geojson_geometry and geojson_geometry["type"] in "Polygon"


def is_multi_polygon(geojson_geometry):
    return (
        isinstance(geojson_geometry, dict) and "type" in geojson_geometry and geojson_geometry["type"] in "MultiPolygon"
    )


def is_feature(feature):
    if isinstance(feature, dict) and "type" in feature and "geometry" in feature and feature["type"] in "Feature":
        return is_polygon_or_multi_polygon(feature["geometry"])


def is_feature_collection(geojson):
    if (
        isinstance(geojson, dict)
        and "type" in geojson
        and "features" in geojson
        and geojson["type"] in "FeatureCollection"
    ):
        return all(is_polygon_or_multi_polygon(feature["geometry"]) for feature in geojson["features"])


def is_geometry_collection(geojson):
    if (
        isinstance(geojson, dict)
        and "type" in geojson
        and "geometries" in geojson
        and geojson["type"] in "GeometryCollection"
    ):
        return all(is_polygon_or_multi_polygon(geometry) for geometry in geojson["geometries"])
