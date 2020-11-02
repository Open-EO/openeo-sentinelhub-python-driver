import datetime
import math

import numpy as np
import xarray as xr
from eolearn.core import EOWorkflow

from ._common import ProcessEOTask, DATA_TYPE_TEMPORAL_INTERVAL, ProcessParameterInvalid


def merge_coords(cube1_dimension, cube2_dimension):
    temporary_merging_dim = "temporary_merging_dim"
    return xr.merge(
        [{temporary_merging_dim: cube1_dimension}, {temporary_merging_dim: cube2_dimension}], compat="no_conflicts"
    )[temporary_merging_dim]


def add_dimension_and_coords(cube, dimension_name, dimension, axis):
    cube = cube.expand_dims(dim={dimension_name: len(dimension)}, axis=axis)
    cube = cube.assign_coords({dimension_name: dimension.data})
    return cube


def get_value(cube, coord):
    try:
        return True, cube.sel(coord).data.tolist()
    except:
        return False, None


class merge_cubesEOTask(ProcessEOTask):
    """
    https://processes.openeo.org/1.0.0/#merge_cubes
    """

    def run_overlap_resolver(self, cube1_value, cube2_value, overlap_resolver):
        dependencies, result_task = self.generate_workflow_dependencies(
            overlap_resolver["process_graph"], {"x": cube1_value, "y": cube2_value}
        )
        workflow = EOWorkflow(dependencies)
        all_results = workflow.execute({})
        result = all_results[result_task]
        return result

    def process(self, arguments):
        cube1 = self.validate_parameter(arguments, "cube1", required=True, allowed_types=[xr.DataArray])
        cube2 = self.validate_parameter(arguments, "cube2", required=True, allowed_types=[xr.DataArray])
        overlap_resolver = self.validate_parameter(arguments, "overlap_resolver", required=False, default=None)
        context = self.validate_parameter(arguments, "context", required=False, default=None)

        # Documentation doesn't make it clear whether cubes with different dimensions and mismatching labels on a common
        # dimension are "compatible" or not.
        # If cubes have different dimensions, we merge them into a higher dimensional cube which includes all, and then
        # merge and resolve overlap in (at most one) common overlapping dimension.
        all_dimensions = tuple(dict.fromkeys(cube1.dims + cube2.dims))
        overlapping_dimension_found = False

        result = xr.DataArray()
        # We iterate over the union of all dimension of the two cubes
        for i, dimension_name in enumerate(all_dimensions):
            # If both cubes have the dimension, we merge the coordinates
            if dimension_name in cube1.dims and dimension_name in cube2.dims:
                dimension = merge_coords(cube1[dimension_name], cube2[dimension_name])
                if (
                    cube1[dimension_name].size != dimension[dimension_name].size
                    or cube1[dimension_name].size != cube2[dimension_name].size
                ):
                    if overlapping_dimension_found:
                        raise ProcessParameterInvalid(
                            "merge_cubes",
                            "cube1/cube2",
                            "Only one of the dimensions can have different labels.",
                        )
                    overlapping_dimension_found = True
            # If only one of the cubes has the dimension, we add it to the other one
            elif dimension_name in cube1.dims:
                dimension = cube1[dimension_name]
                cube2 = add_dimension_and_coords(cube2, dimension_name, dimension, i)
            else:
                dimension = cube2[dimension_name]
                cube1 = add_dimension_and_coords(cube1, dimension_name, dimension, i)

            # We add the dimension and (merged) coordinates to the result
            # We should end up with an empty (filled with `nan`s) DataArray of correct dimensions and coords
            result = add_dimension_and_coords(result, dimension_name, dimension, i)

        # After expand_dims, DataArray is readonly. Workaround is to copy it
        # https://github.com/pydata/xarray/issues/2891#issuecomment-482880911
        result = result.copy()

        # Now we fill our empty array with values for all combinations of coords: https://stackoverflow.com/a/10098162
        dimension_sizes = tuple(result.sizes.values())
        for coord in np.ndindex(dimension_sizes):
            # We get the coord values (timestamp, lat, lng ...) for each position (e.g. at result[0,0,0,0], result[0,0,0,1],...)
            coord_labels = result[coord].coords
            cube1_has_value, cube1_value_at_coord = get_value(cube1, coord_labels)
            cube2_has_value, cube2_value_at_coord = get_value(cube2, coord_labels)

            if cube1_has_value and cube2_has_value:
                if overlap_resolver is None:
                    raise ProcessParameterInvalid(
                        "merge_cubes",
                        "overlap_resolver",
                        "Overlapping data cubes, but no overlap resolver has been specified. (OverlapResolverMissing)",
                    )
                resolved_value = self.run_overlap_resolver(cube1_value_at_coord, cube2_value_at_coord, overlap_resolver)
                result[coord] = resolved_value
            elif cube1_has_value:
                result[coord] = cube1_value_at_coord
            else:
                result[coord] = cube2_value_at_coord

        return result
