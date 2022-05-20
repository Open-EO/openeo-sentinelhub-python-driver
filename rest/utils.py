import json
import glob

from pg_to_evalscript import list_supported_processes


def get_all_process_definitions():
    files = []
    processes = []

    for supported_process in list_supported_processes():
        files.extend(glob.glob(f"process_definitions/{supported_process}.json"))

    for file in files:
        with open(file) as f:
            processes.append(json.load(f))

    return processes