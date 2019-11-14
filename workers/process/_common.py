from copy import deepcopy
from eolearn.core import EOTask
import xarray as xr
import numpy as np

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

class ProcessArgumentInvalid(UserError):
    error_code = "ProcessArgumentInvalid"

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
        for i,v in enumerate(obj):
            yield i,v
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield k,v


class ProcessEOTask(EOTask):
    """ Original EOTask (eolearn package) uses constructor and execute() to
        process data.

        ProcessEOTask:
        - gives us a list of the tasks we depend on (based on arguments - where
          the data comes from)
        - uses execute() to apply the data from previous tasks and from variables to arguments
        - calls process() with these arguments

        In other words, subclasses should only extend process() and leave
        execute() as is.
    """
    def __init__(self, arguments, job_id, logger, variables, node_name):
        self._arguments = arguments
        self._variables = variables
        self._arguments_with_data = None
        self._cached_depends_on = None
        self.node_name = node_name
        self.job_id = job_id
        self.logger = logger
        self.process_id = self.__class__.__name__[:-len("EOTask")]

    @staticmethod
    def _get_from_nodes(arguments):
        """ Process graph dependencies are determined by usage of special
            'from_node' dicts. This function traverses arguments recursively
            and figures out which tasks this task depends on.
        """

        from_nodes = []
        for k, v in iterate(arguments):
            if isinstance(v, dict) and len(v) == 1 and 'from_node' in v:
                from_nodes.append(v['from_node'])
            elif isinstance(v, dict) and len(v) == 1 and 'callback' in v:
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
            if isinstance(v, dict) and len(v) == 1 and 'from_node' in v:
                arguments[k] = values_by_node[v['from_node']]
            elif isinstance(v, dict) and len(v) == 1 and 'variable_id' in v:
                arguments[k] = variables[v['variable_id']]
            elif isinstance(v, dict) and len(v) == 1 and 'callback' in v:
                continue  # we don't traverse callbacks
            elif isinstance(v, dict) or isinstance(v, list):
                ProcessEOTask._apply_data_to_arguments(arguments[k], values_by_node, variables)

    def _update_arguments_with_data(self, prev_results):
        """ prev_results: tuple of previous results, in the same order that
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
        """ Each process EOTask should implement this function instead of using
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
            param_val = arguments.get(param, 'argument not present')
            if param_val == 'argument not present':
                return default

        if not allowed_types:
            return param_val
        types = tuple(allowed_types)
        if not isinstance(param_val, types):
            type_mapping = {
                int: "integer",
                float: "number",
                bool: "boolean",
                type(None): "null",
                xr.DataArray: "xarray.DataArray",
                dict: "object",
                str: "string",
                list: "array",
            }
            types = ",".join(set([type_mapping[typename] for typename in types]))
            raise ProcessArgumentInvalid("The argument '{}' in process '{}' is invalid: Argument must be of types '[{}]'.".format(param, self.process_id, types))

        return param_val


    def convert_to_dataarray(self, data, as_list=False):
        original_type_was_number = True

        if isinstance(data, xr.DataArray):
            return False ,data

        if as_list:
            for i,element in enumerate(data):
                if not isinstance(element, xr.DataArray):
                    data[i] = xr.DataArray(np.array(element, dtype=np.float))
                else:
                    original_type_was_number = False
        else:
            data = xr.DataArray(np.array(data, dtype=np.float))

        return original_type_was_number, data


    def results_in_appropriate_type(self, results, original_type_was_number):
        if original_type_was_number:
            if np.isnan(results):
                return None
            return float(results)
        return results