import warnings
from datetime import datetime, date, timedelta

from sentinelhub import DataCollection, MimeType
from sentinelhub.time_utils import parse_time
from pg_to_evalscript import convert_from_process_graph

from processing.openeo_process_errors import FormatUnsuitable


def check_process_graph_conversion_validity(process_graph):
    results = convert_from_process_graph(process_graph)
    return results[0]["invalid_node_id"]


def get_evalscript(process_graph):
    results = convert_from_process_graph(process_graph)
    return results[0]["evalscript"].write()


def id_to_data_collection(collection_id):
    warnings.warn("id_to_data_collection not implemented yet!")
    return DataCollection.SENTINEL2_L1C


def get_node_by_process_id_from_process_graph(process_graph, process_id):
    for node in process_graph.values():
        if node["process_id"] == process_id:
            return node


def get_collection_from_process_graph(process_graph):
    load_collection_node = get_node_by_process_id_from_process_graph(process_graph, "load_collection")
    return id_to_data_collection(load_collection_node["arguments"]["id"])


def get_bounds_from_process_graph(process_graph):
    """
    Returns bbox, EPSG code, geometry
    """
    load_collection_node = get_node_by_process_id_from_process_graph(process_graph, "load_collection")
    spatial_extent = load_collection_node["arguments"]["spatial_extent"]
    DEFAULT_EPSG_CODE = 4326

    if spatial_extent is None:
        return (0, -90, 360, 90), DEFAULT_EPSG_CODE, None
    elif (
        isinstance(spatial_extent, dict)
        and "type" in spatial_extent
        and spatial_extent["type"] in ("Polygon", "MultiPolygon")
    ):
        return None, DEFAULT_EPSG_CODE, spatial_extent
    else:
        epsg_code = spatial_extent.get("crs", DEFAULT_EPSG_CODE)
        east = spatial_extent["east"]
        west = spatial_extent["west"]
        north = spatial_extent["north"]
        south = spatial_extent["south"]
        return (west, south, east, north), epsg_code, None


def get_maximum_temporal_extent_for_collection(collection):
    warnings.warn("get_maximum_temporal_extent_for_collection not implemented yet!")
    return datetime.now(), datetime.now()


def get_temporal_extent_from_process_graph(process_graph, collection):
    """
    Returns from_time, to_time
    """
    load_collection_node = get_node_by_process_id_from_process_graph(process_graph, "load_collection")
    temporal_extent = load_collection_node["arguments"]["temporal_extent"]
    if temporal_extent is None:
        from_time, to_time = get_maximum_temporal_extent_for_collection(collection)
        return from_time, to_time

    interval_start, interval_end = temporal_extent
    if interval_start is None:
        from_time, _ = get_maximum_temporal_extent_for_collection(collection)
    else:
        from_time = parse_time(interval_start)

    if interval_end is None:
        _, to_time = get_maximum_temporal_extent_for_collection(collection)
    else:
        to_time = parse_time(interval_end)

    # type(d) is date is used because Datetime is a subclass of Date and isinstance(d, Date) is always True
    if type(from_time) is date:
        from_time = datetime(from_time.year, from_time.month, from_time.day)
    if type(to_time) is date:
        to_time = datetime(to_time.year, to_time.month, to_time.day) + timedelta(days=1)

    to_time = to_time - timedelta(milliseconds=1)  # End of the interval is not inclusive
    return from_time, to_time


def format_to_mimetype(output_format):
    OUTPUT_FORMATS = {
        "gtiff": MimeType.TIFF,
        "png": MimeType.PNG,
        "jpeg": MimeType.JPG,
        "json": MimeType.JSON,
    }
    output_format = output_format.lower()
    if output_format in OUTPUT_FORMATS:
        return OUTPUT_FORMATS[output_format]
    else:
        raise FormatUnsuitable()


def get_mimetype_from_process_graph(process_graph):
    save_result_node = get_node_by_process_id_from_process_graph(process_graph, "save_result")
    return format_to_mimetype(save_result_node["arguments"]["format"])


def get_dimensions_from_process_graph(process_graph):
    warnings.warn("get_dimensions_from_process_graph when width and height are not specified not implemented yet!")
    load_collection_node = get_node_by_process_id_from_process_graph(process_graph, "load_collection")
    spatial_extent = load_collection_node["arguments"]["spatial_extent"]
    DEFAULT_WIDTH = 100
    DEFAULT_HEIGHT = 100

    if spatial_extent is None:
        return DEFAULT_WIDTH, DEFAULT_HEIGHT

    width = spatial_extent.get("width", DEFAULT_WIDTH)
    height = spatial_extent.get("height", DEFAULT_HEIGHT)
    return width, height
