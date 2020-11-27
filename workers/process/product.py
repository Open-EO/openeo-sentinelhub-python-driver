import numpy as np

from ._common import ProcessEOTask, ProcessParameterInvalid, DataCube


class productEOTask(ProcessEOTask):
    def process(self, arguments):
        data = self.validate_parameter(arguments, "data", required=True, allowed_types=[DataCube, list])
        ignore_nodata = self.validate_parameter(arguments, "ignore_nodata", default=True, allowed_types=[bool])

        if isinstance(data, DataCube) and data.attrs.get("reduce_by"):
            dim = data.attrs["reduce_by"]
            return data.prod(dim=dim, skipna=ignore_nodata, keep_attrs=True)

        if len(data) < 2:
            raise ProcessParameterInvalid("product", "data", "Array must have at least 2 elements.")

        original_type_was_number, data = self.convert_to_datacube(data, as_list=True)

        multiplication_array = DataCube.concat(data, dim="temporary_multiplication_dim")
        results = multiplication_array.prod(dim="temporary_multiplication_dim", skipna=ignore_nodata, keep_attrs=True)
        return self.results_in_appropriate_type(results, original_type_was_number)
