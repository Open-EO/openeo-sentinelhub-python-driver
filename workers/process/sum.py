import numpy as np
import xarray as xr
xr.set_options(keep_attrs=True)

from ._common import ProcessEOTask, ProcessArgumentInvalid, validate_parameters

class sumEOTask(ProcessEOTask):
    """
        This process is often used within reduce process. Reduce could pass each of the vectors separately, 
        but this would be very inefficient. Instead, we get passed a whole xarray with an attribute reduce_by.
        In order to know, over which dimension should a callback process be applied, reduce appends the
        reduction dimension to the reduce_by attribute of the data. The last element of this list is the current
        reduction dimension. This also allows multi-level reduce calls.
    """
    def process(self, arguments):
        required_params, optional_params = {"data": []}, {"ignore_nodata": [bool]}
        validate_parameters("sum", arguments, required_params=required_params, optional_params=optional_params)

        data,ignore_nodata = arguments["data"], arguments.get("ignore_nodata", True)

        original_type_was_number = False

        if len(data) < 2:
            raise ProcessArgumentInvalid("The argument 'data' in process 'sum' is invalid: Array must have at least 2 elements.")

        for i,element in enumerate(data):
            if not isinstance(element, xr.DataArray):
                original_type_was_number = True
                data[i] = xr.DataArray(np.array(element, dtype=np.float))

        summation_array = xr.concat(data, dim="temporary_summation_dim")
        results = summation_array.sum(dim="temporary_summation_dim", skipna=ignore_nodata, keep_attrs=True)

        if original_type_was_number:
            if np.isnan(results):
                return None
            else:
                return float(results)

        return results

