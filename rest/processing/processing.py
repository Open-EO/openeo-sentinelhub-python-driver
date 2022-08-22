import os

import time

from pg_to_evalscript import convert_from_process_graph
from flask import g
from sentinelhub import BatchRequestStatus, BatchUserAction, SentinelHubBatch

from processing.process import Process
from processing.sentinel_hub import SentinelHub
from processing.partially_supported_processes import partially_supported_processes
from dynamodb.utils import get_user_defined_processes_graphs
from const import openEOBatchJobStatus
from openeoerrors import Timeout


def check_process_graph_conversion_validity(process_graph):
    for partially_supported_process in partially_supported_processes:
        is_valid, error = partially_supported_process(process_graph).is_usage_valid()
        if not is_valid:
            raise error

    partially_supported_processes_as_udp = {
        partially_supported_process.process_id: {} for partially_supported_process in partially_supported_processes
    }
    user_defined_processes_graphs = get_user_defined_processes_graphs()
    user_defined_processes_graphs.update(partially_supported_processes_as_udp)
    results = convert_from_process_graph(process_graph, user_defined_processes=user_defined_processes_graphs)
    return results[0]["invalid_node_id"]


def new_process(process, width=None, height=None):
    user_defined_processes_graphs = get_user_defined_processes_graphs()
    return Process(
        process,
        width=width,
        height=height,
        user=g.get("user"),
        user_defined_processes=user_defined_processes_graphs,
    )


def new_sentinel_hub(deployment_endpoint=None):
    return SentinelHub(user=g.get("user"), service_base_url=deployment_endpoint)


def process_data_synchronously(process, width=None, height=None):
    p = new_process(process, width=width, height=height)
    return p.execute_sync(), p.mimetype.get_string()


def create_batch_job(process):
    return new_process(process).create_batch_job()


def start_new_batch_job(sentinel_hub, process):
    new_batch_request_id, _ = create_batch_job(process)
    sentinel_hub.start_batch_job(new_batch_request_id)
    return new_batch_request_id


def start_batch_job(batch_request_id, process, deployment_endpoint):
    """
    openEO allows starting a batch job regardless of the status, unless it's already running or queued.
    Sentinel Hub Batch API only allows starting the job if it hasn't been run yet.
    If some tiles succeeded and some failed, it allows restarting it.
    Otherwise, we have to create a new job.

    Based on status:
    CREATED: we can start
    ANALYSIS_DONE: we can start
    PARTIAL: we can restart
    DONE: we have to create a new job
    FAILED: we have to create a new job
    CANCELED: we have to create a new job
    ANALYSING + user action START: User started the job and the pre-job analysis is running, we don't do anything
    ANALYSING + user action ANALYSE: Analysis is running, but the job hasn't started. We create a new one.
    PROCESSING: we don't do anything
    """
    sentinel_hub = new_sentinel_hub(deployment_endpoint=deployment_endpoint)
    batch_request_info = sentinel_hub.get_batch_request_info(batch_request_id)

    if batch_request_info is None:
        return start_new_batch_job(sentinel_hub, process)
    elif batch_request_info.status in [BatchRequestStatus.CREATED, BatchRequestStatus.ANALYSIS_DONE]:
        sentinel_hub.start_batch_job(batch_request_id)
    elif batch_request_info.status == BatchRequestStatus.PARTIAL:
        sentinel_hub.restart_batch_job(batch_request_id)
    elif batch_request_info.status in [
        BatchRequestStatus.DONE,
        BatchRequestStatus.FAILED,
        BatchRequestStatus.CANCELED,
    ] or (
        batch_request_info.status == BatchRequestStatus.ANALYSING
        and batch_request_info.user_action == BatchUserAction.ANALYSE
    ):
        return start_new_batch_job(sentinel_hub, process)


def get_batch_request_info(batch_request_id, deployment_endpoint):
    return new_sentinel_hub(deployment_endpoint=deployment_endpoint).get_batch_request_info(batch_request_id)


def cancel_batch_job(batch_request_id, process, deployment_endpoint):
    new_sentinel_hub(deployment_endpoint=deployment_endpoint).cancel_batch_job(batch_request_id)
    return create_batch_job(process)


def delete_batch_job(batch_request_id, deployment_endpoint):
    return new_sentinel_hub(deployment_endpoint=deployment_endpoint).delete_batch_job(batch_request_id)


def modify_batch_job(process):
    """
    Sentinel Hub Batch API only allows modifying the description and output object:
    https://docs.sentinel-hub.com/api/latest/reference/#operation/updateBatchProcessRequest
    However, openEO allows modifying the entire batch job, including the process.
    We therefore have to create a new Sentinel Hub batch request.
    """
    return create_batch_job(process)


def get_batch_job_estimate(batch_request_id, process, deployment_endpoint):
    sentinel_hub = new_sentinel_hub(deployment_endpoint=deployment_endpoint)

    batch_request = sentinel_hub.get_batch_request_info(batch_request_id)

    if batch_request.value_estimate is None:
        analysis_sleep_time_s = 5
        total_sleep_time = 0
        MAX_TOTAL_TIME = 29
        sentinel_hub.start_batch_job_analysis(batch_request_id)

    while batch_request.value_estimate is None and batch_request.status in [
        BatchRequestStatus.CREATED,
        BatchRequestStatus.ANALYSING,
    ]:
        if total_sleep_time + analysis_sleep_time_s > MAX_TOTAL_TIME:
            raise Timeout()

        time.sleep(analysis_sleep_time_s)
        total_sleep_time += analysis_sleep_time_s
        batch_request = sentinel_hub.get_batch_request_info(batch_request_id)

    default_temporal_interval = 3
    estimate_secure_factor = 2

    p = Process(process, user=g.get("user"))
    temporal_interval = p.get_temporal_interval(in_days=True)

    if temporal_interval is None:
        temporal_interval = default_temporal_interval

    estimated_pu = estimate_secure_factor * batch_request.value_estimate * default_temporal_interval / temporal_interval

    n_pixels = batch_request.tile_count * batch_request.tile_width_px * batch_request.tile_height_px
    estimated_file_size = p.estimate_file_size(n_pixels=n_pixels)
    return estimated_pu, estimated_file_size


def get_batch_job_status(batch_request_id, deployment_endpoint):
    batch_request_info = get_batch_request_info(batch_request_id, deployment_endpoint)
    if batch_request_info is not None:
        error = batch_request_info.error if batch_request_info.status == BatchRequestStatus.FAILED else None
        return (
            openEOBatchJobStatus.from_sentinelhub_batch_job_status(
                batch_request_info.status, batch_request_info.user_action
            ),
            error,
        )
    else:
        return openEOBatchJobStatus.FINISHED, None


def create_tpdi_order(collection_id, products, parameters, byoc_collection_id):
    sentinel_hub = new_sentinel_hub()
    return sentinel_hub.create_tpdi_order(collection_id, products, parameters, byoc_collection_id)


def get_all_tpdi_orders():
    sentinel_hub = new_sentinel_hub()
    return sentinel_hub.get_all_tpdi_orders()


def get_tpdi_order(order_id):
    sentinel_hub = new_sentinel_hub()
    return sentinel_hub.get_tpdi_order(order_id)


def delete_tpdi_order(order_id):
    sentinel_hub = new_sentinel_hub()
    return sentinel_hub.delete_tpdi_order(order_id)


def confirm_tpdi_order(order_id):
    sentinel_hub = new_sentinel_hub()
    return sentinel_hub.confirm_tpdi_order(order_id)


def get_user_commercial_data_collection_name(user_id, collection_id):
    return f"{user_id}__{collection_id}"


def search_tpdi_products(collection_id, bbox, intersects, datetime, filter_query, limit):
    sentinel_hub = new_sentinel_hub()
    return sentinel_hub.search_tpdi_products(
        collection_id=collection_id,
        bbox=bbox,
        intersects=intersects,
        datetime=datetime,
        filter_query=filter_query,
        limit=limit,
    )


def create_new_empty_byoc_collection(user_id, collection_id):
    sentinel_hub = new_sentinel_hub()
    name = get_user_commercial_data_collection_name(user_id=user_id, collection_id=collection_id)
    USER_COMMERCIAL_DATA_BUCKET = os.environ.get("USER_COMMERCIAL_DATA_BUCKET")
    return sentinel_hub.create_byoc_collection(name=name, aws_bucket=USER_COMMERCIAL_DATA_BUCKET)["id"]


def get_byoc_collection_id(user_id, collection_id):
    sentinel_hub = new_sentinel_hub()
    name = get_user_commercial_data_collection_name(user_id=user_id, collection_id=collection_id)
    collections = sentinel_hub.query_byoc_collections(search=name)

    for collection in collections:
        if collection["name"] == name:
            return collection["id"]
