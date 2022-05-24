import os
import json
import glob

from pg_to_evalscript import list_supported_processes

from processing.utils import iterate


def get_abs_file_path(rel_file_path):
    script_dir = os.path.dirname(__file__)
    return os.path.join(script_dir, rel_file_path)


def get_all_process_definitions():
    files = []
    processes = []

    for supported_process in list_supported_processes():
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
