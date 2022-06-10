import time

from pg_to_evalscript import convert_from_process_graph
from flask import g
from sentinelhub import BatchRequestStatus, BatchUserAction, SentinelHubBatch

from processing.process import Process
from processing.sentinel_hub import SentinelHub
from dynamodb.utils import get_user_defined_processes_graphs


def check_process_graph_conversion_validity(process_graph):
    user_defined_processes_graphs = get_user_defined_processes_graphs()
    results = convert_from_process_graph(process_graph, user_defined_processes=user_defined_processes_graphs)
    return results[0]["invalid_node_id"]


def get_sh_access_token():
    if g.get("user"):
        return g.user.sh_access_token


def new_process(process, width=None, height=None):
    user_defined_processes_graphs = get_user_defined_processes_graphs()
    return Process(
        process,
        width=width,
        height=height,
        access_token=get_sh_access_token(),
        user_defined_processes=user_defined_processes_graphs,
    )


def new_sentinel_hub():
    return SentinelHub(access_token=get_sh_access_token())


def process_data_synchronously(process, width=None, height=None):
    p = new_process(process, width=width, height=height)
    return p.execute_sync(), p.mimetype.get_string()


def create_batch_job(process):
    return new_process(process).create_batch_job()


def start_batch_job(batch_request_id, process):
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
    sentinel_hub = new_sentinel_hub()
    batch_request_info = sentinel_hub.get_batch_request_info(batch_request_id)

    if batch_request_info.status in [BatchRequestStatus.CREATED, BatchRequestStatus.ANALYSIS_DONE]:
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
        new_batch_request_id = create_batch_job(process)
        sentinel_hub.start_batch_job(new_batch_request_id)
        return new_batch_request_id


def get_batch_request_info(batch_request_id):
    return new_sentinel_hub().get_batch_request_info(batch_request_id)


def cancel_batch_job(batch_request_id, process):
    new_sentinel_hub().cancel_batch_job(batch_request_id)
    return create_batch_job(process)


def delete_batch_job(batch_request_id):
    return new_sentinel_hub().delete_batch_job(batch_request_id)


def modify_batch_job(process):
    """
    Sentinel Hub Batch API only allows modifying the description and output object:
    https://docs.sentinel-hub.com/api/latest/reference/#operation/updateBatchProcessRequest
    However, openEO allows modifying the entire batch job, including the process.
    We therefore have to create a new Sentinel Hub batch request.
    """
    return create_batch_job(process)


def get_batch_job_estimate(batch_request_id, process):
    sentinel_hub = new_sentinel_hub()

    batch_request = sentinel_hub.get_batch_request_info(batch_request_id)

    if batch_request.value_estimate is None:
        analysis_sleep_time_s = 5
        sentinel_hub.start_batch_job_analysis(batch_request_id)

    while batch_request.value_estimate is None and batch_request.status in [
        BatchRequestStatus.CREATED,
        BatchRequestStatus.ANALYSING,
    ]:
        time.sleep(analysis_sleep_time_s)
        batch_request = sentinel_hub.get_batch_request_info(batch_request_id)

    default_temporal_interval = 3
    estimate_secure_factor = 2

    p = Process(process, access_token=g.user.sh_access_token)
    temporal_interval = p.get_temporal_interval(in_days=True)

    if temporal_interval is None:
        temporal_interval = default_temporal_interval

    estimated_pu = estimate_secure_factor * batch_request.value_estimate * default_temporal_interval / temporal_interval

    n_pixels = batch_request.tile_count * batch_request.tile_width_px * batch_request.tile_height_px
    estimated_file_size = p.estimate_file_size(n_pixels=n_pixels)
    return estimated_pu, estimated_file_size
