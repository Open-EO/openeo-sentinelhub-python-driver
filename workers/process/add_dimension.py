import xarray as xr

from ._common import ProcessEOTask, ProcessParameterInvalid


class add_dimensionEOTask(ProcessEOTask):
    """
    https://processes.openeo.org/1.0.0/#add_dimension
    """

    def process(self, arguments):
        data = self.validate_parameter(arguments, "data", required=True, allowed_types=[xr.DataArray])
        name = self.validate_parameter(arguments, "name", required=True, allowed_types=[str])
        label = self.validate_parameter(arguments, "label", required=True, allowed_types=[str, float])
        dimension_type = self.validate_parameter(
            arguments, "type", required=False, allowed_types=[str], default="other"
        )

        if name in data.dims:
            raise ProcessParameterInvalid(
                "add_dimension", "name", "A dimension with the specified name already exists."
            )

        result = data.expand_dims(dim=name)
        result = result.assign_coords({name: [label]})
        return result
