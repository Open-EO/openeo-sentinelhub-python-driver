from copy import deepcopy
import datetime
import re

import dask.array as da
from eolearn.core import EOTask
import numpy as np
import xarray as xr
import process

# additional datatypes which do not have corresponding pairs in python:
DATA_TYPE_TEMPORAL_INTERVAL = "temporal-interval"


TYPE_MAPPING = {
    int: "integer",
    float: "number",
    bool: "boolean",
    type(None): "null",
    xr.DataArray: "raster-cube",
    dict: "object",
    str: "string",
    list: "array",
    DATA_TYPE_TEMPORAL_INTERVAL: "temporal-interval",
}


# These exceptions should translate to the list of OpenEO error codes:
#   https://api.openeo.org/1.0.0/errors.json


class ExecFailedError(Exception):
    def __init__(self, msg):
        self.msg = msg


class UserError(ExecFailedError):
    http_code = 400


class Internal(ExecFailedError):
    error_code = "Internal"
    http_code = 500


class ProcessParameterInvalid(UserError):
    error_code = "ProcessParameterInvalid"

    def __init__(self, process_id, parameter, reason):
        super().__init__(f"The value passed for parameter '{parameter}' in process '{process_id}' is invalid: {reason}")


class VariableValueMissing(UserError):
    error_code = "VariableValueMissing"


class ProcessUnsupported(UserError):
    error_code = "ProcessUnsupported"


class ProcessArgumentRequired(UserError):
    error_code = "ProcessArgumentRequired"


class StorageFailure(Internal):
    error_code = "StorageFailure"


# internal exceptions:
class ValidationError(Exception):
    def __init__(self, msg):
        self.msg = msg


def iterate(obj):
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            yield i, v
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v


def parse_rfc3339(dt, default_h=0, default_m=0, default_s=0):
    g = re.match(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})([ Tt]([0-9]{2}):([0-9]{2}):([0-9]{2})(\.([0-9]+))?[Z]?)?$", dt)
    return datetime.datetime(
        year=int(g.group(1)),
        month=int(g.group(2)),
        day=int(g.group(3)),
        hour=int(g.group(4)) if g.group(4) is not None else 0,
        minute=int(g.group(5)) if g.group(5) is not None else 0,
        second=int(g.group(6)) if g.group(6) is not None else 0,
        microsecond=int(g.group(8)) if g.group(8) is not None else 0,
    )


def _validate_temporal_interval(param):
    if not isinstance(param, list) or len(param) != 2:
        raise ValidationError("Expecting a list with exactly 2 elements.")
    if param[0] is None and param[1] is None:
        raise ValidationError("At least one of the interval boundaries must not be null.")
    result = [
        None if param[0] is None else parse_rfc3339(param[0]),
        None if param[1] is None else parse_rfc3339(param[1]),
    ]
    return result


class ProcessEOTask(EOTask):
    """Original EOTask (eolearn package) uses constructor and execute() to
    process data.

    ProcessEOTask:
    - gives us a list of the tasks we depend on (based on arguments - where
      the data comes from)
    - uses execute() to apply the data from previous tasks and from variables to arguments
    - calls process() with these arguments

    In other words, subclasses should only extend process() and leave
    execute() as is.

    Params:
    - arguments: node arguments as specified in the process graph
    - variables: provided upon execution by the service - should replace the values in arguments appropriately (this class takes care of that)
    - job_metadata: additional data that was provided when the job was started (for example auth_token)
    """

    def __init__(self, arguments, job_id, logger, variables, node_name, job_metadata):
        self._arguments = arguments
        self._variables = variables
        self._arguments_with_data = None
        self._cached_depends_on = None
        self.node_name = node_name
        self.job_id = job_id
        self.logger = logger
        self.job_metadata = job_metadata
        self.process_id = self.__class__.__name__[: -len("EOTask")]

    @staticmethod
    def _get_from_nodes(arguments):
        """Process graph dependencies are determined by usage of special
        'from_node' dicts. This function traverses arguments recursively
        and figures out which tasks this task depends on.
        """

        from_nodes = []
        for k, v in iterate(arguments):
            if isinstance(v, dict) and len(v) == 1 and "from_node" in v:
                from_nodes.append(v["from_node"])
            elif isinstance(v, dict) and len(v) == 1 and "process_graph" in v:
                # we don't traverse callbacks, because they might have their own
                # 'from_node' arguments, but on a deeper level:
                continue
            elif isinstance(v, dict) or isinstance(v, list):
                from_nodes.extend(ProcessEOTask._get_from_nodes(v))

        return from_nodes

    def depends_on(self):
        if not self._cached_depends_on:
            self._cached_depends_on = list(set(ProcessEOTask._get_from_nodes(self._arguments)))
        return self._cached_depends_on

    @staticmethod
    def _apply_data_to_arguments(arguments, values_by_node, variables):
        for k, v in iterate(arguments):
            if isinstance(v, dict) and len(v) == 1 and "from_node" in v:
                arguments[k] = values_by_node[v["from_node"]]
            elif isinstance(v, dict) and len(v) == 1 and "variable_id" in v:
                arguments[k] = variables[v["variable_id"]]
            elif isinstance(v, dict) and len(v) == 1 and "process_graph" in v:
                continue  # we don't traverse callbacks
            elif isinstance(v, dict) or isinstance(v, list):
                ProcessEOTask._apply_data_to_arguments(arguments[k], values_by_node, variables)

    def _update_arguments_with_data(self, prev_results):
        """prev_results: tuple of previous results, in the same order that
        depends_on() returned.
        """
        self._arguments_with_data = deepcopy(self._arguments)
        values_by_node = dict(zip(self.depends_on(), prev_results))
        ProcessEOTask._apply_data_to_arguments(self._arguments_with_data, values_by_node, self._variables)

    def execute(self, *prev_results):
        self.logger.debug("[{}]: updating arguments for task {}...".format(self.job_id, self.__class__.__name__))
        self._update_arguments_with_data(prev_results)
        self.logger.debug("[{}]: executing task {}...".format(self.job_id, self.__class__.__name__))
        result = self.process(self._arguments_with_data)
        self.logger.debug("[{}]: task {} executed, returning result.".format(self.job_id, self.__class__.__name__))
        return result

    def process(self, arguments_with_data):
        """Each process EOTask should implement this function instead of using
        execute(). The arguments already have all relevant vars substituded
        for values ('from_node',...).
        """
        raise Exception("This process is not implemented yet.")

    def validate_parameter(self, arguments, param, required=False, allowed_types=[], default=None):
        if required:
            try:
                param_val = arguments[param]
            except KeyError:
                raise ProcessArgumentRequired("Process '{}' requires argument '{}'.".format(self.process_id, param))
        else:
            if param not in arguments:
                return default
            param_val = arguments[param]

        if not allowed_types:
            return param_val

        # if parameter is int and we expect a number (float), convert automatically:
        if isinstance(param_val, int) and float in allowed_types:
            param_val = float(param_val)

        allowed_types_str = ",".join([TYPE_MAPPING[typename] for typename in allowed_types])

        # xr.DataArray might be simulating another data type:
        if isinstance(param_val, xr.DataArray) and param_val.attrs.get("simulated_datatype", None):
            if param_val.attrs["simulated_datatype"][0] not in allowed_types:
                raise ProcessParameterInvalid(
                    self.process_id, param, f"Argument must be of types '[{allowed_types_str}]'."
                )
            else:
                return param_val

        # check if param matches temporal-interval data type:
        if DATA_TYPE_TEMPORAL_INTERVAL in allowed_types:
            try:
                param_val = _validate_temporal_interval(param_val)
                return param_val
            except ValidationError as ex:
                if len(allowed_types) == 1:
                    raise ProcessParameterInvalid(self.process_id, param, ex.msg)
                else:
                    pass  # parameter might still match other (less restrictive) data types

        if not isinstance(param_val, tuple(allowed_types)):
            raise ProcessParameterInvalid(self.process_id, param, f"Argument must be of types '[{allowed_types_str}]'.")
        else:
            return param_val

    def convert_to_dataarray(self, data, as_list=False):
        original_type_was_number = True

        if isinstance(data, xr.DataArray):
            return False, data

        if as_list:
            model = None
            for element in data:
                if isinstance(element, xr.DataArray):
                    model = element
                    original_type_was_number = False
                    break

            for i, element in enumerate(data):
                if isinstance(element, (int, float, type(None))):
                    ######################################################################
                    # This is an inefficient hotfix to handle mixed lists of numbers and
                    # DataArrays in processes such as sum, subtract, multiply, divide.
                    if model is not None:
                        new_data = element * da.ones_like(model, chunks=1000)
                        number_array = model.copy(data=new_data)
                        data[i] = number_array
                    ######################################################################
                    else:
                        data[i] = xr.DataArray(np.array(element, dtype=np.float))
                elif not isinstance(element, xr.DataArray):
                    raise ProcessParameterInvalid(
                        self.process_id,
                        "data",
                        "Elements of the array must be of types '[number, null, raster-cube]'.",
                    )

        else:
            data = xr.DataArray(np.array(data, dtype=np.float))

        return original_type_was_number, data

    def results_in_appropriate_type(self, results, original_type_was_number):
        if original_type_was_number:
            if np.isnan(results):
                return None
            return float(results)
        return results

    def generate_workflow_dependencies(self, graph, parent_arguments):
        def set_from_parameters(args, parent_arguments):
            for key, value in iterate(args):
                if isinstance(value, dict) and len(value) == 1 and "from_parameter" in value:
                    args[key] = parent_arguments[value["from_parameter"]]
                elif isinstance(value, dict) and len(value) == 1 and "process_graph" in value:
                    continue
                elif isinstance(value, dict) or isinstance(value, list):
                    args[key] = set_from_parameters(value, parent_arguments)

            return args

        result_task = None
        tasks = {}
        graph = deepcopy(graph)

        for node_name, node_definition in graph.items():
            node_arguments = node_definition["arguments"]
            node_arguments = set_from_parameters(node_arguments, parent_arguments)

            class_name = node_definition["process_id"] + "EOTask"
            class_obj = getattr(getattr(process, node_definition["process_id"]), class_name)
            full_node_name = f"{self.node_name}/{node_name}"
            tasks[node_name] = class_obj(
                node_arguments, self.job_id, self.logger, self._variables, full_node_name, self.job_metadata
            )

            if node_definition.get("result", False):
                result_task = tasks[node_name]

        dependencies = []
        for node_name, task in tasks.items():
            depends_on = [tasks[x] for x in task.depends_on()]
            dependencies.append((task, depends_on, "Node name: " + node_name))

        return dependencies, result_task


# Class Band() allows us to treat band aliases and wavelengths as an integral part of band coordinates.
# Example:
#   x = xr.DataArray([[1], [2], [3]], dims=("x", "bands"), coords={"x": [11, 22, 33], "bands": [Band("B01", "myalias", 0.543)]})
class Band(object):
    def __init__(self, name, alias=None, wavelength=None):
        self.name = name
        self.alias = alias
        self.wavelength = wavelength

    def __eq__(self, other):
        # when comparing to an object (of type Band), we would like the objects to be completely equal:
        if isinstance(other, Band):
            return self.name == other.name and self.alias == other.alias and self.wavelength == other.wavelength
        # however, when comparing to a string, equality means something else - either a name or alias must match:
        if isinstance(other, str):
            return self.name == other or self.alias == other
        # when comparing to a number, we compare wavelengths:
        if isinstance(other, float):
            # note that we must not try to convert to float - when comparing, caller must explicitly use a float if they want to compare wavelengths
            if self.wavelength is None:
                return False
            return self.wavelength == other
        return False

    def __ge__(self, other):
        # when comparing to a number, we compare wavelengths:
        if isinstance(other, float):
            if self.wavelength is None:
                return False
            return self.wavelength >= other
        return self.name >= other.name

    def __gt__(self, other):
        # when comparing to a number, we compare wavelengths:
        if isinstance(other, float):
            if self.wavelength is None:
                return False
            return self.wavelength > other
        return self.name > other.name

    def __le__(self, other):
        # when comparing to a number, we compare wavelengths:
        if isinstance(other, float):
            if self.wavelength is None:
                return True
            return self.wavelength <= other
        return self.name <= other.name

    def __lt__(self, other):
        # when comparing to a number, we compare wavelengths:
        if isinstance(other, float):
            if self.wavelength is None:
                return True
            return self.wavelength < other
        return self.name < other.name

    def __repr__(self):
        if self.alias is None and self.wavelength is None:
            return f"Band({repr(self.name)})"
        return f"Band({repr(self.name)}, {repr(self.alias)}, {repr(self.wavelength)})"

    def __hash__(self):
        return self.name.__hash__()


# sorts xr.DataArray by dims and coords so that we can compare it more easily:
def _sort_by_dims_coords(x_original):
    x = x_original.copy(deep=False)
    for dim in x.dims:
        x = x.sortby(dim)
    x = x.transpose(*sorted(list(x.dims)))
    return x


def assert_allclose(x, y):
    # comparison should not depend on the order of dims or coords:
    x = _sort_by_dims_coords(x)
    y = _sort_by_dims_coords(y)
    xr.testing.assert_allclose(x, y)
