import numpy as np
import xarray as xr

xr.set_options(keep_attrs=True)

from ._common import ProcessEOTask, ProcessParameterInvalid, DataCube


class sumEOTask(ProcessEOTask):
    """
    This process is often used within reduce_dimension process, which could pass each of the vectors separately,
    but this would be very inefficient. Instead, we get passed a whole xarray with an attribute reduce_by.
    In order to know, over which dimension should a callback process be applied, reduce_dimension appends the
    reduction dimension to the reduce_by attribute of the data. The last element of this list is the current
    reduction dimension. This also allows multi-level reduce_dimension calls.
    """

    def process(self, arguments):
        data = self.validate_parameter(arguments, "data", required=True, allowed_types=[xr.DataArray, list])
        ignore_nodata = self.validate_parameter(arguments, "ignore_nodata", default=True, allowed_types=[bool])

        if isinstance(data, xr.DataArray) and data.attrs.get("reduce_by"):
            dim = data.attrs["reduce_by"]
            return data.sum(dim=dim, skipna=ignore_nodata, keep_attrs=True)

        if len(data) < 2:
            raise ProcessParameterInvalid("sum", "data", "Array must have at least 2 elements.")

        original_type_was_number, data = self.convert_to_datacube(data, as_list=True)

        summation_array = DataCube.concat(data, dim="temporary_summation_dim")
        results = summation_array.sum(dim="temporary_summation_dim", skipna=ignore_nodata, keep_attrs=True)

        return self.results_in_appropriate_type(results, original_type_was_number)
