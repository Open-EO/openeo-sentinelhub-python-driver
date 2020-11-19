from ._common import ProcessEOTask, ProcessParameterInvalid, iterate
from eolearn.core import EOWorkflow
import xarray as xr
import process
from ._common import DataCube, DimensionType


class reduce_dimensionEOTask(ProcessEOTask):
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
            return DataCube.from_dataarray(data.squeeze(dimension, drop=True))

        if not data.attrs.get("reduce_by"):
            arguments["data"].attrs["reduce_by"] = [dimension]
        else:
            arguments["data"].attrs["reduce_by"].append(dimension)

        dependencies, result_task = self.generate_workflow_dependencies(reducer["process_graph"], arguments)
        workflow = EOWorkflow(dependencies)
        all_results = workflow.execute({})
        result = all_results[result_task]

        result.attrs["reduce_by"].pop()
        result.attrs["simulated_datatype"] = None

        if target_dimension:
            result = DataCube.from_dataarray(xr.concat(result, dim=target_dimension), data.get_dim_types())

        return result
