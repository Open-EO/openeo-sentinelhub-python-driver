def iterate(obj):
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            yield i, v
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v


def inject_variables_in_process_graph(pg_object, variables):
    """
    Injects variables into the object in place.
    """
    for key, value in iterate(pg_object):
        if isinstance(value, dict) and len(value) == 1 and "from_parameter" in value:
            if value["from_parameter"] in variables:
                pg_object[key] = variables[value["from_parameter"]]
        elif isinstance(value, dict) or isinstance(value, list):
            inject_variables_in_process_graph(value, variables)
