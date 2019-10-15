from ._common import ProcessEOTask, ProcessArgumentInvalid, ProcessArgumentRequired, iterate
from eolearn.core import EOWorkflow
import process

class reduceEOTask(ProcessEOTask):
    def generate_workflow_dependencies(self, graph, parent_arguments):

        def set_from_arguments(args, parent_arguments):
            for key, value in iterate(args):
                if isinstance(value, dict) and len(value) == 1 and 'from_argument' in value:
                    args[key] = parent_arguments[value["from_argument"]]
                elif isinstance(value, dict) and len(value) == 1 and 'callback' in value:
                    continue
                elif isinstance(value, dict) or isinstance(value, list):
                    args[key] = set_from_arguments(value, parent_arguments)

            return args

        result_task = None
        tasks = {}

        for node_name, node_definition in graph.items():
            node_arguments = node_definition["arguments"]
            node_arguments = set_from_arguments(node_arguments, parent_arguments)

            class_name = node_definition["process_id"] + "EOTask"
            class_obj = getattr(getattr(process,node_definition["process_id"]), class_name)
            tasks[node_name] = class_obj(node_arguments, "some_job_id", None)

            if node_definition.get('result', False):
                result_task = tasks[node_name]

        dependencies = []
        for node_name, task in tasks.items():
            depends_on = [tasks[x] for x in task.depends_on()]
            dependencies.append((task, depends_on, 'Node name: ' + node_name))

        return dependencies, result_task


    def process(self, arguments):
        try:
            data = arguments["data"]
        except:
            raise ProcessArgumentRequired("Process 'reduce' requires argument 'data'.")

        try:
            dimension = arguments["dimension"]

            if dimension not in data.dims:
                raise ProcessArgumentInvalid("The argument 'dimension' in process 'reduce' is invalid: Dimension '{}' does not exist in data.".format(dimension))
        except:
            raise ProcessArgumentRequired("Process 'reduce' requires argument 'dimension'.")

        reducer = arguments.get("reducer")
        target_dimension = arguments.get("target_dimension")
        binary = arguments.get("binary", False)

        if reducer is None:
            if data[dimension].size > 1:
                raise ProcessArgumentInvalid("The argument 'dimension' in process 'reduce' is invalid: Dimension '{}' has more than one value, but reducer is not specified.".format(dimension))
            return data.squeeze(dimension, drop=True)
        else:
            if not data.attrs.get("reduce_by"):
                arguments["data"].attrs["reduce_by"] = [dimension]
            else:
                arguments["data"].attrs["reduce_by"].append(dimension)

            dependencies, result_task = self.generate_workflow_dependencies(reducer["callback"], arguments)
            workflow = EOWorkflow(dependencies)
            all_results = workflow.execute({})
            result = all_results[result_task]

            result.attrs["reduce_by"].pop()

            if target_dimension:
                result = xr.concat(results, dim=target_dimension)

            return result
