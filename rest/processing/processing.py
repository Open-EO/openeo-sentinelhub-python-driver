from processing.pg_conversion import (
    get_evalscript,
    get_bounds_from_process_graph,
    get_collection_from_process_graph,
    get_temporal_extent_from_process_graph,
    get_mimetype_from_process_graph,
    get_dimensions_from_process_graph,
)
from processing.sentinel_hub import create_processing_request


def process_data_synchronously(process):
    process_graph = process["process_graph"]
    evalscript = get_evalscript(process_graph)
    bbox, epsg_code, geometry = get_bounds_from_process_graph(process_graph)
    collection = get_collection_from_process_graph(process_graph)
    from_date, to_date = get_temporal_extent_from_process_graph(process_graph, collection)
    mimetype = get_mimetype_from_process_graph(process_graph)
    width, height = get_dimensions_from_process_graph(process_graph)
    return (
        create_processing_request(
            bbox=bbox,
            epsg_code=epsg_code,
            geometry=geometry,
            collection=collection,
            evalscript=evalscript,
            from_date=from_date,
            to_date=to_date,
            width=width,
            height=height,
            mimetype=mimetype,
        ),
        mimetype.get_string(),
    )
