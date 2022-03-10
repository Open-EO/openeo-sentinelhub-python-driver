from pg_to_evalscript import convert_from_process_graph

from processing.process import Process
from processing.sentinel_hub import SentinelHub


def check_process_graph_conversion_validity(process_graph):
    results = convert_from_process_graph(process_graph)
    return results[0]["invalid_node_id"]


def process_data_synchronously(process, width=None, height=None):
    p = Process(process, width=width, height=height)
    return p.execute_sync(), p.mimetype


def create_batch_job(process):
    p = Process(process)
    return p.create_batch_job()


def start_batch_job(batch_request_id):
    sentinel_hub = SentinelHub()
    sentinel_hub.start_batch_job(batch_request_id)


def get_batch_request_info(batch_request_id):
    sentinel_hub = SentinelHub()
    return sentinel_hub.get_batch_request_info(batch_request_id)


def cancel_batch_job(batch_request_id, process):
    sentinel_hub = SentinelHub()
    sentinel_hub.cancel_batch_job(batch_request_id)
    return create_batch_job(process)


def delete_batch_job(batch_request_id):
    sentinel_hub = SentinelHub()
    return sentinel_hub.delete_batch_job(batch_request_id)


def modify_batch_job(process):
    """
    Sentinel Hub Batch API only allows modifying the description and output object:
    https://docs.sentinel-hub.com/api/latest/reference/#operation/updateBatchProcessRequest
    However, openEO allows modifying the entire batch job, including the process.
    We therefore have to create a new Sentinel Hub batch request.
    """
    return create_batch_job(process)
