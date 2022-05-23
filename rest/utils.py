import os
import json
import glob

from pg_to_evalscript import list_supported_processes


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
