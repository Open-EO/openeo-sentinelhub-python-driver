import xarray as xr

from datetime import datetime

from ._common import ProcessEOTask, ProcessParameterInvalid, parse_rfc3339, Band


def generate_dimension_coord_values(labels, dimension_type):
    if dimension_type == "bands":
        return [Band(l) for l in labels]
    if dimension_type == "temporal":
        return [parse_rfc3339(label) for label in labels]
    return labels


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

        if dimension_type not in ["spatial", "temporal", "bands", "other"]:
            raise ProcessParameterInvalid(
                "add_dimension", "type", "Argument must be one of ['spatial', 'temporal', 'bands', 'other']."
            )

        if name in data.dims:
            raise ProcessParameterInvalid(
                "add_dimension", "name", "A dimension with the specified name already exists. (DimensionExists)"
            )

        result = data.expand_dims(dim=name)
        result = result.assign_coords({name: generate_dimension_coord_values([label], dimension_type)})
        return result
