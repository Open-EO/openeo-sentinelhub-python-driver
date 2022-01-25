import warnings
from datetime import datetime, timedelta

from sentinelhub import DataCollection
from sentinelhub.time_utils import iso_to_datetime
from pg_to_evalscript import convert_from_process_graph


def check_process_graph_conversion_validity(process_graph):
    results = convert_from_process_graph(process_graph)
    return results[0]["invalid_node_id"]


def get_evalscript(process_graph):
    results = convert_from_process_graph(process_graph)
    return results[0]["evalscript"].write()


def id_to_data_collection(collection_id):
    warnings.warn("id_to_data_collection not implemented yet!")
    return DataCollection.SENTINEL2_L1C


def get_collection_from_process_graph(process_graph):
    for node in process_graph.values():
        if node["process_id"] == "load_collection":
            return id_to_data_collection(node["arguments"]["id"])


def get_bounds_from_process_graph(process_graph):
    """
    Returns bbox, CRS, geometry
    """
    spatial_extent = process_graph["spatial_extent"]

    if spatial_extent is None:
        return (0, -90, 360, 90), None, None
    elif (
        isinstance(spatial_extent, dict)
        and "type" in spatial_extent
        and spatial_extent["type"] in ("Polygon", "MultiPolygon")
    ):
        return None, None, spatial_extent
    else:
        crs = spatial_extent.get("crs", 4326)
        east = spatial_extent["east"]
        west = spatial_extent["west"]
        north = spatial_extent["north"]
        south = spatial_extent["south"]
        return (west, south, east, north), crs, None


def get_maximum_temporal_extent_for_collection(collection):
    warnings.warn("get_maximum_temporal_extent_for_collection not implemented yet!")
    return datetime.now(), datetime.now()


def get_temporal_extent_from_process_graph(process_graph, collection):
    """
    Returns from_time, to_time
    """
    temporal_extent = process_graph["spatial_extent"]
    if temporal_extent is None:
        from_time, to_time = get_maximum_temporal_extent_for_collection(collection)
        return from_time, to_time

    interval_start, interval_end = temporal_extent
    if interval_start is None:
        from_time, _ = get_maximum_temporal_extent_for_collection(collection)
    else:
        from_time = iso_to_datetime(interval_end)

    if interval_end is None:
        _, to_time = get_maximum_temporal_extent_for_collection(collection)
    else:
        to_time = iso_to_datetime(interval_end)

    to_time = to_time - timedelta(milliseconds=1)  # End of the interval is not inclusive
    return from_time, to_time


def format_to_mimetype(output_format):
    OUTPUT_FORMATS = {
        "gtiff": "image/tiff",
        "png": "image/png",
        "jpeg": "image/jpeg",
        "json": "application/json",
    }
    if output_format in OUTPUT_FORMATS:
        return OUTPUT_FORMATS[output_format]
    else:
        raise Exception("Output format not supported.")


def get_mimetype_from_process_graph(process_graph):
    for node in process_graph.values():
        if node["process_id"] == "save_result":
            return format_to_mimetype(node["arguments"]["format"])


def get_dimensions_from_process_graph(process_graph):
    warnings.warn("get_dimensions_from_process_graph when width and height are not specified not implemented yet!")
    spatial_extent = process_graph["spatial_extent"]
    DEFAULT_WIDTH = 100
    DEFAULT_HEIGHT = 100

    if spatial_extent is None:
        return DEFAULT_WIDTH, DEFAULT_HEIGHT

    width = spatial_extent.get("width", DEFAULT_WIDTH)
    height = spatial_extent.get("height", DEFAULT_HEIGHT)
    return width, height
