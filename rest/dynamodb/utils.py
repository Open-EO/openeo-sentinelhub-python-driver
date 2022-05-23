from flask import g

from .dynamodb import ProcessGraphsPersistence


def get_all_user_defined_processes():
    all_user_defined_processes = []
    for record in ProcessGraphsPersistence.query_by_user_id(g.user.user_id):
        all_user_defined_processes.append(record)
    return all_user_defined_processes


def get_user_defined_processes_graphs():
    user_defined_processes_graphs = dict()
    all_user_defined_processes = get_all_user_defined_processes()
    for user_defined_process in all_user_defined_processes:
        user_defined_processes_graphs[user_defined_process["id"]] = user_defined_process["process_graph"]
    return user_defined_processes_graphs
