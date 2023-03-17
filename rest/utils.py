import os
import json
import glob
import warnings

from sentinelhub.time_utils import parse_time

from pg_to_evalscript import list_supported_processes

from processing.utils import iterate


def get_abs_file_path(rel_file_path):
    script_dir = os.path.dirname(__file__)
    return os.path.join(script_dir, rel_file_path)


def get_all_process_definitions():
    from processing.partially_supported_processes import partially_supported_processes

    files = []
    processes = []

    partially_supported_processes_ids = [
        partially_supported_process.process_id for partially_supported_process in partially_supported_processes
    ]

    for supported_process in list_supported_processes() + partially_supported_processes_ids:
        files.extend(glob.glob(get_abs_file_path(f"process_definitions/{supported_process}.json")))

    for file in files:
        with open(file) as f:
            processes.append(json.load(f))

    return processes


def get_parameter_defs_dict(process_graph, params):
    """
    Converts API-style parameter definition (array of dicts) into openeo_pg_parser compatible format (dict, name: schema)
    If specified parameters for UDP are None, we take all parameters in the process graph and pass them as global parameters
    That way we ensure all parameters are defined, as it's difficult to determine true expected parameters if not listed.
    """
    parameters = {}
    if params is not None:
        for param in params:
            parameters[param["name"]] = param["schema"]
    else:
        all_parameters = get_undefined_parameters(process_graph, all_parameters=[])
        for param in all_parameters:
            # Set some placeholder value
            parameters[param] = None
    return parameters


def get_undefined_parameters(process_graph, all_parameters=[]):
    for key, value in iterate(process_graph):
        if isinstance(value, dict) and len(value) == 1 and "from_parameter" in value:
            all_parameters.append(value["from_parameter"])
        elif isinstance(value, dict) or isinstance(value, list):
            return get_undefined_parameters(value, all_parameters)
    return all_parameters


def enrich_user_defined_processes_with_parameters(user_defined_processes):
    for user_defined_process in user_defined_processes:
        if "parameters" not in user_defined_process or user_defined_process["parameters"] is None:
            params = get_undefined_parameters(user_defined_process["process_graph"], all_parameters=[])
            for i in range(len(params)):
                params[i] = {"name": params[i]}
            user_defined_process["parameters"] = params
    return user_defined_processes


def get_env_var(var_name, required=True):
    env_var = os.environ.get(var_name)
    if env_var is None and required:
        raise Exception(f"Environment variable '{var_name}' must be defined!")
    elif env_var is None:
        warnings.warn(f"Environment variable '{var_name}' is not defined!")
    return env_var


def get_data_from_bucket(s3, bucket_name, batch_request_id):
    continuation_token = None
    results = []

    while True:
        if continuation_token:
            response = s3.list_objects_v2(
                Bucket=bucket_name, Prefix=batch_request_id, ContinuationToken=continuation_token
            )
        else:
            response = s3.list_objects_v2(Bucket=bucket_name, Prefix=batch_request_id)
        results.extend(response["Contents"])
        if response["IsTruncated"]:
            continuation_token = response["NextContinuationToken"]
        else:
            break

    return results


ISO8601_UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def convert_timestamp_to_simpler_format(datetime_str):
    return parse_time(datetime_str).strftime(ISO8601_UTC_FORMAT)


def get_roles(object_key):
    if object_key.lower().endswith(".json"):
        return ["metadata"]
    return ["data"]
