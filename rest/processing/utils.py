import math
import copy

from pyproj import CRS, Transformer
from shapely.geometry import shape, mapping
from pg_to_evalscript.process_graph_utils import get_dependencies, get_dependents
from sentinelhub import ResamplingType

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


def degree_to_meter(degree):
    return (6378137.0 * math.pi * degree) / 180


def convert_degree_resolution_to_meters(degrees):
    x = degrees[0]
    y = degrees[1]
    return [degree_to_meter(x), degree_to_meter(y)]


def convert_extent_to_epsg4326(extent):
    crs = extent.get("crs", 4326)

    if crs == 4326:
        return extent

    east, north = convert_to_epsg4326(crs, extent["east"], extent["north"])
    west, south = convert_to_epsg4326(crs, extent["west"], extent["south"])

    return {"crs": 4326, "east": east, "north": north, "west": west, "south": south}


def convert_to_epsg4326(crs, x, y):
    crs = CRS.from_epsg(crs)
    crs_4326 = CRS.from_epsg(4326)
    transformer = Transformer.from_crs(crs, crs_4326, always_xy=True)
    return transformer.transform(x, y)


def convert_extent_to_geojson(extent):
    east = extent["east"]
    north = extent["north"]
    west = extent["west"]
    south = extent["south"]
    return construct_geojson(west, south, east, north)


def construct_geojson(west, south, east, north):
    return {
        "type": "Polygon",
        "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
    }


def convert_geometry_crs(geometry, crs):
    crs = CRS.from_epsg(crs)
    crs_4326 = CRS.from_epsg(4326)
    transformer = Transformer.from_crs(crs_4326, crs, always_xy=True)
    geojson = mapping(geometry)

    new_coordinates = []
    for coord in geojson["coordinates"][0]:
        x, y = transformer.transform(coord[0], coord[1])
        new_coordinates.append([x, y])

    geojson["coordinates"] = [new_coordinates]
    return shape(geojson)


def convert_bbox_crs(bbox, crs_from, crs_to):
    west, south, east, north = bbox
    crs_from = CRS.from_epsg(crs_from)
    crs_to = CRS.from_epsg(crs_to)
    transformer = Transformer.from_crs(crs_from, crs_to, always_xy=True)
    west, south = transformer.transform(west, south)
    east, north = transformer.transform(east, north)
    return (west, south, east, north)


def replace_from_node(node, node_id_to_replace, new_node_id):
    for key, value in iterate(node):
        if (
            isinstance(value, dict)
            and len(value) == 1
            and "from_node" in value
            and value["from_node"] == node_id_to_replace
        ):
            value["from_node"] = new_node_id
        elif isinstance(value, dict) or isinstance(value, list):
            replace_from_node(value, node_id_to_replace, new_node_id)


def remove_node_from_process_graph(process_graph, node_id):
    dependencies = get_dependencies(process_graph)
    dependents = get_dependents(dependencies)

    parent_node = dependencies[node_id].pop()
    for dependent_node_id in dependents[node_id]:
        # Replace all `from_node` in dependent nodes with the node id of the parent process
        replace_from_node(process_graph[dependent_node_id], node_id, parent_node)

    del process_graph[node_id]


def remove_partially_supported_processes_from_process_graph(process_graph, partially_defined_processes):
    all_occurrences = []
    process_graph = copy.deepcopy(process_graph)

    for partially_defined_process in partially_defined_processes:
        all_occurrences.extend(partially_defined_process(process_graph).get_all_occurrences())

    for occurrence in all_occurrences:
        remove_node_from_process_graph(process_graph, occurrence["node_id"])

    return process_graph


def convert_projection_to_epsg_code(projection):
    crs = CRS(projection)
    return crs.to_epsg()


def get_spatial_info_from_partial_processes(partially_supported_processes, process_graph):
    final_geometry = None
    final_crs = 4326
    final_resolution = None
    final_resampling_method = ResamplingType.NEAREST

    for partially_supported_process in partially_supported_processes:
        geometry, crs, resolution, resampling_method = partially_supported_process(process_graph).get_spatial_info()

        if geometry:
            if final_geometry is None:
                final_geometry = geometry
            else:
                final_geometry = final_geometry.intersection(geometry)

        if crs is not None:
            final_crs = crs

        if resolution is not None:
            final_resolution = resolution

        if resampling_method is not None:
            final_resampling_method = resampling_method

    return final_geometry, final_crs, final_resolution, final_resampling_method


def get_node_by_process_id(process_graph, process_id):
    for node in process_graph.values():
        if node["process_id"] == process_id:
            return node


def overwrite_spatial_extent_without_parameters(process_graph):
    # https://github.com/Open-EO/openeo-web-editor/issues/277#issuecomment-1246989125
    required_params = ["spatial_extent_west", "spatial_extent_south", "spatial_extent_east", "spatial_extent_north"]
    load_collection_node = get_node_by_process_id(process_graph, "load_collection")

    for cardinal_direction in ["east", "west", "south", "north"]:
        cardinal_direction_value = load_collection_node["arguments"]["spatial_extent"][cardinal_direction]
        if isinstance(cardinal_direction_value, dict) and "from_parameter" in cardinal_direction_value:
            return process_graph

    for cardinal_direction in ["east", "west", "south", "north"]:
        load_collection_node["arguments"]["spatial_extent"][cardinal_direction] = {
            "from_parameter": f"spatial_extent_{cardinal_direction}"
        }

    return process_graph
