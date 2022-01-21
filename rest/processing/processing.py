from processing.pg_conversion import get_evalscript

def process_data_synchronously(process):
    process_graph = process["process_graph"]
    evalscript = get_evalscript(process_graph)
    collection = get_collection_from_process_graph(process_graph)
    return create_processing_request(collection=collection, evalscript=evalscript)