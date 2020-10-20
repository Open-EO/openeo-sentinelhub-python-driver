import datetime
import math
from copy import deepcopy

import numpy as np
import xarray as xr
from eolearn.core import EOWorkflow

from ._common import ProcessEOTask, DATA_TYPE_TEMPORAL_INTERVAL, ProcessParameterInvalid, iterate
import process


def merge_coords(cube1_dimension, cube2_dimension):
    temporary_merging_dim = "temporary_merging_dim"
    return xr.merge(
        [{temporary_merging_dim: cube1_dimension}, {temporary_merging_dim: cube2_dimension}], compat="no_conflicts"
    )[temporary_merging_dim]


def get_value(cube, coord):
    try:
        return cube.sel(coord).data.tolist()
    except:
        return None


def run_overlap_resolver(cube1_value, cube2_value, overlap_resolver, logger=None):
    dependencies, result_task = generate_workflow_dependencies(
        overlap_resolver["process_graph"], {"x": cube1_value, "y": cube2_value}, logger=logger
    )
    workflow = EOWorkflow(dependencies)
    all_results = workflow.execute({})
    result = all_results[result_task]
    return result


def generate_workflow_dependencies(
    graph, parent_arguments, job_id=None, logger=None, _variables=None, job_metadata=None, process_node_name=None
):
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
        full_node_name = f"{process_node_name}/{node_name}"
        tasks[node_name] = class_obj(node_arguments, job_id, logger, _variables, full_node_name, job_metadata)

        if node_definition.get("result", False):
            result_task = tasks[node_name]

    dependencies = []
    for node_name, task in tasks.items():
        depends_on = [tasks[x] for x in task.depends_on()]
        dependencies.append((task, depends_on, "Node name: " + node_name))

    return dependencies, result_task


class merge_cubesEOTask(ProcessEOTask):
    """
    https://processes.openeo.org/1.0.0/#merge_cubes
    """

    def process(self, arguments):
        cube1 = self.validate_parameter(arguments, "cube1", required=True, allowed_types=[xr.DataArray])
        cube2 = self.validate_parameter(arguments, "cube2", required=True, allowed_types=[xr.DataArray])
        overlap_resolver = self.validate_parameter(arguments, "overlap_resolver", required=False, default=None)
        context = self.validate_parameter(arguments, "context", required=False, default=None)

        all_dimensions = tuple(dict.fromkeys(cube1.dims + cube2.dims))
        result = xr.DataArray()

        for i, dimension_name in enumerate(all_dimensions):
            if dimension_name in cube1.dims and dimension_name in cube2.dims:
                dimension = merge_coords(cube1[dimension_name], cube2[dimension_name])
            elif dimension_name in cube1.dims:
                dimension = cube1[dimension_name]
            else:
                dimension = cube2[dimension_name]
            result = result.expand_dims(dim={dimension_name: len(dimension)}, axis=i)
            result = result.assign_coords({dimension_name: dimension.data})

        dimension_sizes = result.sizes
        result = result.copy()  # https://github.com/pydata/xarray/issues/2891#issuecomment-482880911

        for i in range(result.size):
            coord = tuple([i % dimension_sizes[dimension_name] for dimension_name in all_dimensions])
            coord_labels = result[coord].coords
            cube1_value_at_coord = get_value(cube1, coord_labels)
            cube2_value_at_coord = get_value(cube2, coord_labels)

            if (
                cube1_value_at_coord is not None
                and cube2_value_at_coord is not None
                and cube1_value_at_coord != cube2_value_at_coord
            ):
                resolved_value = run_overlap_resolver(
                    cube1_value_at_coord, cube2_value_at_coord, deepcopy(overlap_resolver), logger=self.logger
                )
                result[coord] = resolved_value
            elif cube1_value_at_coord is not None:
                result[coord] = cube1_value_at_coord
            else:
                result[coord] = cube2_value_at_coord

        return result
