from ._common import ProcessEOTask, ProcessParameterInvalid, iterate, DataCube
from eolearn.core import EOWorkflow
import process


class applyEOTask(ProcessEOTask):
    def generate_workflow_dependencies(self, graph, parent_data):
        def set_from_parameters(args, parent_data):
            for key, value in iterate(args):
                if isinstance(value, dict) and len(value) == 1 and "from_parameter" in value:
                    args[key] = parent_data
                elif isinstance(value, dict) and len(value) == 1 and "process_graph" in value:
                    continue
                elif isinstance(value, dict) or isinstance(value, list):
                    args[key] = set_from_parameters(value, parent_data)

            return args

        result_task = None
        tasks = {}

        for node_name, node_definition in graph.items():
            node_arguments = node_definition["arguments"]
            node_arguments = set_from_parameters(node_arguments, parent_data)

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
        data = self.validate_parameter(arguments, "data", required=True, allowed_types=[DataCube])
        process = self.validate_parameter(arguments, "process", required=True)

        # marking the data will change the `data` attributes, so we need to do shallow copy (we don't change the
        # data here, so there is no need for deep copy)
        data = data.copy(deep=False)
        # mark the data - while it is still an xarray DataArray, the operations can only be applied to each element:
        data.attrs["simulated_datatype"] = (float,)

        dependencies, result_task = self.generate_workflow_dependencies(process["process_graph"], data)
        workflow = EOWorkflow(dependencies)
        all_results = workflow.execute({})

        result = all_results[result_task]

        # we expect the result to be simulated numbers, but then we return it as datacube:
        if result.attrs["simulated_datatype"][0] != float:
            raise ProcessParameterInvalid(
                "apply", "process", "Result of process callback should be of types [number,null]"
            )
        # no need to make a (shallow) copy of result, since we are the only ones who can use this result; we
        # can just unmark the simulated datatype and return the datacube:
        result.attrs["simulated_datatype"] = None

        return result
