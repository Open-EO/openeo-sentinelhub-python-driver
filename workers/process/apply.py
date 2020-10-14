from ._common import ProcessEOTask, ProcessParameterInvalid, iterate
from eolearn.core import EOWorkflow
import xarray as xr
import process


class applyEOTask(ProcessEOTask):
    def generate_workflow_dependencies(self, graph, parent_data):
        def set_from_arguments(args, parent_data):
            for key, value in iterate(args):
                if isinstance(value, dict) and len(value) == 1 and "from_argument" in value:
                    args[key] = parent_data
                elif isinstance(value, dict) and len(value) == 1 and "callback" in value:
                    continue
                elif isinstance(value, dict) or isinstance(value, list):
                    args[key] = set_from_arguments(value, parent_data)

            return args

        result_task = None
        tasks = {}

        for node_name, node_definition in graph.items():
            node_arguments = node_definition["arguments"]
            node_arguments = set_from_arguments(node_arguments, parent_data)

            class_name = node_definition["process_id"] + "EOTask"
            class_obj = getattr(getattr(process, node_definition["process_id"]), class_name)
            full_node_name = f"{self.node_name}/{node_name}"
            tasks[node_name] = class_obj(
                node_arguments, self.job_id, self.logger, {}, full_node_name, self.job_metadata
            )

            if node_definition.get("result", False):
                if result_task:
                    raise ProcessParameterInvalid(
                        node_definition["process_id"],
                        "result",
                        "Only one node in a (sub)graph can have result set to true.",
                    )
                result_task = tasks[node_name]

        dependencies = []
        for node_name, task in tasks.items():
            depends_on = [tasks[x] for x in task.depends_on()]
            dependencies.append((task, depends_on, "Node name: " + node_name))

        return dependencies, result_task

    def process(self, arguments):
        data = self.validate_parameter(arguments, "data", required=True, allowed_types=[xr.DataArray])
        process = self.validate_parameter(arguments, "process", required=True)

        # mark the data - while it is still an xarray DataArray, the operations can only be applied to each element:
        if not data.attrs.get("simulated_datatype"):
            data.attrs["simulated_datatype"] = []
        data.attrs["simulated_datatype"].append((float,))

        dependencies, result_task = self.generate_workflow_dependencies(process["callback"], data)
        workflow = EOWorkflow(dependencies)
        all_results = workflow.execute({})

        # the returned data should no longer be treated as numbers:
        all_results[result_task].attrs["simulated_datatype"].pop()
        return all_results[result_task]
