from copy import deepcopy
from eolearn.core import EOTask


class ExecFailedError(Exception):
    def __init__(self, msg):
        self.msg = msg
        self.error_code = 400


class InvalidInputError(ExecFailedError):
    pass

class ServiceFailure(Exception):
    def __init__(self, msg):
        self.msg = msg
        self.error_code = 500


class ProcessEOTask(EOTask):
    """ Original EOTask (eolearn package) uses constructor and execute() to
        process data.

        ProcessEOTask:
        - gives us a list of the tasks we depend on (based on arguments - where
          the data comes from)
        - uses execute() to apply the data from previous tasks to arguments
        - calls process() with these arguments

        In other words, subclasses should only extend process() and leave
        execute() as is.
    """
    def __init__(self, arguments, job_id, logger):
        self._arguments = arguments
        self._arguments_with_data = None
        self._cached_depends_on = None
        self.job_id = job_id
        self.logger = logger

    @staticmethod
    def _get_from_nodes(arguments):
        """ Process graph dependencies are determined by usage of special
            'from_node' dicts. This function traverses arguments recursively
            and figures out which tasks this task depends on.
        """
        from_nodes = []
        for k, v in arguments.items():
            if isinstance(v, dict) and len(v) == 1 and 'from_node' in v:
                from_nodes.append(v['from_node'])
            elif isinstance(v, dict) and len(v) == 1 and 'callback' in v:
                # we don't traverse callbacks, because they might have their own
                # 'from_node' arguments, but on a deeper level:
                continue
            elif isinstance(v, dict):
                from_nodes.extend(ProcessEOTask._get_from_nodes(v))

        return from_nodes

    def depends_on(self):
        if not self._cached_depends_on:
            self._cached_depends_on = list(set(ProcessEOTask._get_from_nodes(self._arguments)))
        return self._cached_depends_on

    @staticmethod
    def _apply_data_to_arguments(arguments, values_by_node):
        for k, v in arguments.items():
            if isinstance(v, dict) and len(v) == 1 and 'from_node' in v:
                arguments[k] = values_by_node[v['from_node']]
            elif isinstance(v, dict) and len(v) == 1 and 'callback' in v:
                continue  # we don't traverse callbacks
            elif isinstance(v, dict):
                ProcessEOTask._apply_data_to_arguments(arguments[k], values_by_node)

    def _update_arguments_with_data(self, prev_results):
        """ prev_results: tuple of previous results, in the same order that
                depends_on() returned.
        """
        self._arguments_with_data = deepcopy(self._arguments)
        values_by_node = dict(zip(self.depends_on(), prev_results))
        ProcessEOTask._apply_data_to_arguments(self._arguments_with_data, values_by_node)


    def execute(self, *prev_results):
        self._update_arguments_with_data(prev_results)
        return self.process(self._arguments_with_data)

    def process(self, arguments_with_data):
        """ Each process EOTask should implement this function instead of using
            execute(). The arguments already have all relevant vars substituded
            for values ('from_node',...).
        """
        raise Exception("This process is not implemented yet.")
