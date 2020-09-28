import numpy as np
import xarray as xr
xr.set_options(keep_attrs=True)

from ._common import ProcessEOTask, ProcessArgumentInvalid, ProcessArgumentRequired

class array_elementEOTask(ProcessEOTask):
    """
        This process is often used within reduce_dimension process. Reduce could pass each of the vectors separately,
        but this would be very inefficient. Instead, we get passed a whole xarray with an attribute reduce_by.
        In order to know, over which dimension should a callback process be applied, reduce_dimension appends the
        reduction dimension to the reduce_by attribute of the data. The last element of this list is the current
        reduction dimension. This also allows multi-level reduce_dimension calls.
    """
    def process(self, arguments):
        data = self.validate_parameter(arguments, "data", required=True, allowed_types=[xr.DataArray, list])
        index = self.validate_parameter(arguments, "index", required=True, allowed_types=[int])
        return_nodata = self.validate_parameter(arguments, "return_nodata", default=False, allowed_types=[bool])

        if isinstance(data, xr.DataArray) and data.attrs and data.attrs.get("reduce_by"):
            dim = data.attrs.get("reduce_by")[-1]
            try:
                return data.isel({dim: index})
            except IndexError:
                if return_nodata:
                    """
                        According to documentation (https://open-eo.github.io/openeo-api/processreference/#array_element):
                            '''return_nodata: By default this process throws an IndexOutOfBounds exception if the index is invalid. If you want to return null instead, set this flag to true.'''
                        Thus, our understanding is that the array_element process should return a result of the same shape as a valid index would, but with all values set to null.
                        No elegant solution using the existing instance of DataArray with numpy or xarray functions was found, so we construct a new DataArray and copy the attributes.
                    """
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
