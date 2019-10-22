import numpy as np
import xarray as xr
xr.set_options(keep_attrs=True)

from ._common import ProcessEOTask, ProcessArgumentInvalid, ProcessArgumentRequired

class array_elementEOTask(ProcessEOTask):
    """
        This process is often used within reduce process. Reduce could pass each of the vectors separately, 
        but this would be very inefficient. Instead, we get passed a whole xarray with an attribute reduce_by.
        In order to know, over which dimension should a callback process be applied, reduce appends the
        reduction dimension to the reduce_by attribute of the data. The last element of this list is the current
        reduction dimension. This also allows multi-level reduce calls.
    """
    def process(self, arguments):
        try:
            data = arguments["data"]
            if not isinstance(data, (list,xr.DataArray)):
                raise ProcessArgumentInvalid("The argument 'data' in process 'array_element' is invalid: Argument must be of type 'array'.")
        except:
            raise ProcessArgumentRequired("Process 'array_element' requires argument 'data'.")

        try:
            index = arguments["index"]
            if not isinstance(index, int):
                raise ProcessArgumentInvalid("The argument 'index' in process 'array_element' is invalid: Argument must be of type 'integer'.")
        except:
            raise ProcessArgumentRequired("Process 'array_element' requires argument 'index'.")

        return_nodata = arguments.get("return_nodata", False)

        if not isinstance(return_nodata, bool):
            raise ProcessArgumentInvalid("The argument 'return_nodata' in process 'array_element' is invalid: Argument must be of type 'boolean'.")

        if isinstance(data, xr.DataArray) and data.attrs and data.attrs.get("reduce_by"):
            dim = data.attrs.get("reduce_by")[-1]
            try:
                return data.isel({dim: index})
            except IndexError:
                if return_nodata:
                    new_shape = list(data.values.shape)
                    del new_shape[data.dims.index(dim)]
                    new_values = np.nan * np.ones(new_shape)
                    new_dims = list(data.dims)
                    new_dims.remove(dim)
                    return xr.DataArray(new_values, dims=new_dims, coords=data.coords, attrs=data.attrs)
                raise ProcessArgumentInvalid("The argument 'index' in process 'array_element' is invalid: Index out of bounds.")
        else:
            try:
                return data[index]
            except IndexError:
                if return_nodata:
                    return None
                raise ProcessArgumentInvalid("The argument 'index' in process 'array_element' is invalid: Index out of bounds.")
