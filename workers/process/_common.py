from copy import deepcopy
from eolearn.core import EOTask
import xarray as xr
import numpy as np
import dask.array as da


TYPE_MAPPING = {
    int: "integer",
    float: "number",
    bool: "boolean",
    type(None): "null",
    xr.DataArray: "raster-cube",
    dict: "object",
    str: "string",
    list: "array",
}


# These exceptions should translate to the list of OpenEO error codes:
#   https://open-eo.github.io/openeo-api/errors/#openeo-error-codes


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


def iterate(obj):
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            yield i, v
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v


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
            elif isinstance(v, dict) and len(v) == 1 and "callback" in v:
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
            elif isinstance(v, dict) and len(v) == 1 and "callback" in v:
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
        if isinstance(param_val, xr.DataArray) and len(param_val.attrs.get("simulated_datatype", [])) > 0:
            if param_val.attrs["simulated_datatype"][-1][0] not in allowed_types:
                raise ProcessParameterInvalid(
                    self.process_id, param, f"Argument must be of types '[{allowed_types_str}]'."
                )

        if not isinstance(param_val, tuple(allowed_types)):
            raise ProcessParameterInvalid(self.process_id, param, f"Argument must be of types '[{allowed_types_str}]'.")

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
