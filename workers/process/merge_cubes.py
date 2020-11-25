import datetime
import math

import numpy as np
import xarray as xr
from eolearn.core import EOWorkflow

from ._common import ProcessEOTask, DATA_TYPE_TEMPORAL_INTERVAL, ProcessParameterInvalid, DataCube


def merge_attrs(attrs1, attrs2):
    merged_attrs = {}

    bbox1 = attrs1.get("bbox")
    bbox2 = attrs2.get("bbox")
    if bbox1 != bbox2:
        raise ProcessParameterInvalid(
            "merge_cubes", "cube1/cube2", "Cubes are not compatible - bounding box is not the same."
        )
    if bbox1 is not None:
        merged_attrs["bbox"] = bbox1

    return merged_attrs


class merge_cubesEOTask(ProcessEOTask):
    """
    https://processes.openeo.org/1.0.0/#merge_cubes
    """

    def run_overlap_resolver(self, x, y, overlap_resolver):
        if overlap_resolver is None:
            raise ProcessParameterInvalid(
                "merge_cubes",
                "overlap_resolver",
                "Overlapping data cubes, but no overlap resolver has been specified (OverlapResolverMissing).",
            )

        # we want to treat each number in the cube independently:
        x.attrs["simulated_datatype"] = (float,)
        y.attrs["simulated_datatype"] = (float,)
        dependencies, result_task = self.generate_workflow_dependencies(
            overlap_resolver["process_graph"], {"x": x, "y": y}
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
        # dimension are "compatible" or not. To keep things simple(r), we only allow a single dimension to be different.

        # This process operates in three different modes:
        # - the cubes have the same dimensions and coords
        # - the cubes have the same dims and all coords except on a single dim
        # - one of the cubes is missing one dimension entirely - its values are then broadcasted (with resolver) over each coord in this dimension

        # find if there is a dimension that is missing from one of the cubes entirely:
        missing_dims = list(set(cube1.dims) - set(cube2.dims)) + list(set(cube2.dims) - set(cube1.dims))
        if len(missing_dims) > 1:
            raise ProcessParameterInvalid(
                "merge_cubes",
                "cube1/cube2",
                f"Too many missing dimensions ({', '.join(sorted(missing_dims))}), can be at most one.",
            )

        # find if there are any other dimensions with mismatching coords:
        common_dimensions = set(cube1.dims).intersection(cube2.dims)
        mismatched_dims = missing_dims[:]
        for dim in common_dimensions:
            coords1 = set(cube1.coords[dim].to_index())
            coords2 = set(cube2.coords[dim].to_index())
            if coords1 == coords2:
                continue
            mismatched_dims.append(dim)
        if len(mismatched_dims) > 1:
            raise ProcessParameterInvalid(
                "merge_cubes",
                "cube1/cube2",
                f"Too many mismatched dimensions ({', '.join(sorted(mismatched_dims))}), can be at most one.",
            )

        # if the cubes' dims and coords match completely, we can run overlap resolver and we are done:
        if len(mismatched_dims) == 0:
            result = self.run_overlap_resolver(cube1, cube2, overlap_resolver)
            return result

        # One of the cubes is missing one dimension entirely - we expand its dims to include it, then assign the coords
        # from the other cube. Note that we can't switch the cubes because overlap_resolver might depend on the order
        # (e.g. subtract).
        if len(missing_dims) > 0:
            dim = missing_dims[0]
            if len(cube1.dims) < len(cube2.dims):
                new_coords = cube2.coords[dim]
                cube1 = cube1.expand_dims(
                    {dim: len(new_coords)}, dim_types={dim: cube2.get_dim_type(dim)}
                )  # this copies data over the new dim N-times
                # we can have a dimension without coords, in which case we do not assign them:
                if dim in cube2.coords:
                    cube1 = cube1.assign_coords({dim: new_coords})
            else:
                new_coords = cube1.coords[dim]
                cube2 = cube2.expand_dims({dim: len(new_coords)}, dim_types={dim: cube1.get_dim_type(dim)})
                if dim in cube1.coords:
                    cube2 = cube2.assign_coords({dim: new_coords})

        # this is the dimension over which we:
        # - run overlap_resolver for overlapping coords
        # - concatenate other coords
        dim = mismatched_dims[0]
        dim_type = cube1.get_dim_type(dim)
        result = None
        # first add all coords from cube1 (check for overlap at every step)
        for c in cube1.coords[dim].to_index():
            cube1_part = cube1.sel({dim: c})

            if c in cube2.coords[dim]:
                cube2_part = cube2.sel({dim: c})
                result_part = self.run_overlap_resolver(cube1_part, cube2_part, overlap_resolver)
            else:
                result_part = cube1_part
            # merge the existing result:
            result = result_part if result is None else DataCube.concat([result, result_part], dim=dim)

        # then add all the remaining coords from cube2 (no need for overlap_resolver, there can be no overlap)
        remaining_coords = set(cube2.coords[dim].to_index()) - set(cube1.coords[dim].to_index())
        for c in remaining_coords:
            result_part = cube2.sel({dim: c})
            result = result_part if result is None else DataCube.concat([result, result_part], dim=dim)

        result.set_dim_type(dim, dim_type)
        result.attrs = merge_attrs(cube1.attrs, cube2.attrs)
        return result
