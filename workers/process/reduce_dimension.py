from ._common import ProcessEOTask, ProcessParameterInvalid, iterate
from eolearn.core import EOWorkflow
import xarray as xr
import process


class reduce_dimensionEOTask(ProcessEOTask):
    def generate_workflow_dependencies(self, graph, parent_arguments):
        def set_from_arguments(args, parent_arguments):
            for key, value in iterate(args):
                if isinstance(value, dict) and len(value) == 1 and "from_argument" in value:
                    args[key] = parent_arguments[value["from_argument"]]
                elif isinstance(value, dict) and len(value) == 1 and "process_graph" in value:
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

    def process(self, arguments):
        data = self.validate_parameter(arguments, "data", required=True, allowed_types=[xr.DataArray])
        dimension = self.validate_parameter(arguments, "dimension", required=True, allowed_types=[str])
        reducer = self.validate_parameter(arguments, "reducer", default=None)
        target_dimension = self.validate_parameter(
            arguments, "target_dimension", default=None, allowed_types=[str, type(None)]
        )

        if dimension not in data.dims:
            raise ProcessParameterInvalid(
                "reduce_dimension", "dimension", f"Dimension '{dimension}' does not exist in data."
            )

        if reducer is None:
            if data[dimension].size > 1:
                raise ProcessParameterInvalid(
                    "reduce_dimension",
                    "dimension",
                    f"Dimension '{dimension}' has more than one value, but reducer is not specified.",
                )
            return data.squeeze(dimension, drop=True)
        else:
            if not data.attrs.get("reduce_by"):
                arguments["data"].attrs["reduce_by"] = [dimension]
            else:
                arguments["data"].attrs["reduce_by"].append(dimension)

            dependencies, result_task = self.generate_workflow_dependencies(reducer["process_graph"], arguments)
            workflow = EOWorkflow(dependencies)
            all_results = workflow.execute({})
            result = all_results[result_task]

            result.attrs["reduce_by"].pop()

            if target_dimension:
                result = xr.concat(result, dim=target_dimension)

            return result
