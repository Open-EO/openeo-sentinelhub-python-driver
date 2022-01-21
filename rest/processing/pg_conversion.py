from pg_to_evalscript import convert_from_process_graph, get_collection_from_process_graph

def check_process_graph_conversion_validity(process_graph):
    results = convert_from_process_graph(process_graph)
    return results[0]['invalid_node_id']

def get_evalscript(process_graph):
    results = convert_from_process_graph(process_graph)
    return results[0]['evalscript'].write()

def get_collection_from_process_graph(process_graph):
    for node in process_graph.values():
        if node["process_id"] == "load_collection":
            return node["arguments"]["id"]

def get_output_format_from_process_graph(process_graph):
    for node in process_graph.values():
        if node["process_id"] == "save_result":
            return node["arguments"]["format"]