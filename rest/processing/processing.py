from pg_to_evalscript import convert_from_process_graph

from processing.process import Process


def check_process_graph_conversion_validity(process_graph):
    results = convert_from_process_graph(process_graph)
    return results[0]["invalid_node_id"]


def process_data_synchronously(process):
    p = Process(process)
    return p.execute_sync(), p.mimetype
