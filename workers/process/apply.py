from ._common import ProcessEOTask, ProcessArgumentInvalid, ProcessArgumentRequired, iterate
from eolearn.core import EOWorkflow
import xarray as xr
import process

class applyEOTask(ProcessEOTask):
    def generate_workflow_dependencies(self, graph, parent_arguments):
        def set_from_arguments(args, parent_arguments):
            for key, value in iterate(args):
                if isinstance(value, dict) and len(value) == 1 and 'from_argument' in value:
                    args[key] = parent_arguments["data"]
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
            full_node_name = f'{self.node_name}/{node_name}'
            tasks[node_name] = class_obj(node_arguments, self.job_id, self.logger, {}, full_node_name, self.job_metadata)

            if node_definition.get('result', False):
                result_task = tasks[node_name]

        dependencies = []
        for node_name, task in tasks.items():
            depends_on = [tasks[x] for x in task.depends_on()]
            dependencies.append((task, depends_on, 'Node name: ' + node_name))

        return dependencies, result_task


    def process(self, arguments):
        data = self.validate_parameter(arguments, "data", required=True, allowed_types=[xr.DataArray])
        process = self.validate_parameter(arguments, "process", required=True)

        dependencies, result_task = self.generate_workflow_dependencies(process["callback"], arguments)
        workflow = EOWorkflow(dependencies)
        all_results = workflow.execute({})
        return all_results[result_task]