from eolearn.core import EOWorkflow
import numpy as np
import rasterio.features
import rasterio.transform

from ._common import ProcessEOTask, ProcessParameterInvalid, DataCube, DimensionType


class aggregate_spatialEOTask(ProcessEOTask):
    """
    https://processes.openeo.org/1.0.0/#aggregate_spatial
    """

    def process(self, arguments):
        data = self.validate_parameter(arguments, "data", required=True, allowed_types=[DataCube])
        geometries = self.validate_parameter(arguments, "geometries", required=True, allowed_types=[list])
        reducer = self.validate_parameter(arguments, "reducer", required=True)
        target_dimension = self.validate_parameter(
            arguments, "target_dimension", default="result", allowed_types=[str, type(None)]
        )

        # given the geometries, extend the cube along "result" dimension so that for each coord (geometry) the values are masked. We use rasterio for that.
        # save total_count (x * y)
        # for each geometry save "valid_count" (number of non-masked pixels)
        # stack x and y together, so that we can reduce by joint dimension (spatial - "_xy")
        # run reducer over the cube, reducing by _xy
        # add result_meta dimension; existing coord is "value"
        # add coords "total_count" and "valid_count" to cube and fill with values

        bbox = data.attrs["bbox"]
        xmin, ymin = bbox.lower_left
        xmax, ymax = bbox.upper_right
        w, h = len(data.coords["x"]), len(data.coords["y"])
        transform = rasterio.transform.from_bounds(xmin, ymin, xmax, ymax, w, h)
        # https://rasterio.readthedocs.io/en/latest/api/rasterio.features.html#rasterio.features.rasterize
        out_shape = (
            h,
            w,
        )
        geometry_masks = []
        data_per_geom = None
        for i, geometry in enumerate(geometries):
            geometry_mask = rasterio.features.rasterize(
                [geometry], transform=transform, all_touched=False, out_shape=out_shape
            )
            geometry_masks.append(geometry_mask)

            mask = DataCube(
                geometry_mask,
                dims=(
                    "y",
                    "x",
                ),
            )
            mask = mask.expand_dims({"t": len(data.coords["t"])})
            mask = mask.transpose(*data.dims)
            mask = mask ^ 1  # replace 1 with 0 and 0 with 1

            data2 = data.copy(deep=True)  # we need this, otherwise the mask will be applied to the original data
            masked_data = np.ma.masked_array(data2.values, mask=mask)
            masked_data_xr = DataCube(masked_data, dims=data.dims)
            data_per_geom = (
                masked_data_xr.expand_dims(dim="result")
                if data_per_geom is None
                else DataCube.concat([data_per_geom, masked_data_xr], dim="result")
            )

        # merge "x" and "y" dimension into one, so that we can reduce along it:
        data_stacked_spatial = data_per_geom.stack(_xy=("x", "y"))
        data_stacked_spatial.attrs["reduce_by"] = ["_xy"]
        parent_arguments = {
            "data": data_stacked_spatial,
        }
        dependencies, result_task = self.generate_workflow_dependencies(reducer["process_graph"], parent_arguments)
        workflow = EOWorkflow(dependencies)
        all_results = workflow.execute({})
        result = all_results[result_task]

        for a in ["reduce_by", "bbox", "simulated_datatype"]:
            if a in result.attrs:
                del result.attrs[a]

        # now, final step - add another dimension ("result_meta") and save the total_count and valid_count to it:
        result = result.expand_dims({"result_meta": 3})
        result = result.assign_coords({"result_meta": ["value", "total_count", "valid_count"]})
        result = result.assign_coords({"t": data.coords["t"]})
        result = result.copy()  # not sure why - we need to copy, otherwise assignment below fails (readonly)
        total_count = h * w
        result.loc[dict(result_meta="total_count")] = total_count
        for i, geometry_mask in enumerate(geometry_masks):
            result.loc[dict(result_meta="valid_count", result=i)] = geometry_mask.sum()
        result.set_dim_type("t", data.get_dim_type("t"))
        return result
