import datetime

import numpy as np
import xarray as xr

xr.set_options(keep_attrs=True)

from ._common import ProcessEOTask, ProcessParameterInvalid, parse_rfc3339


class array_elementEOTask(ProcessEOTask):
    """
    This process is often used within reduce_dimension process, which could pass each of the vectors separately,
    but this would be very inefficient. Instead, we get passed a whole xarray with an attribute reduce_by.
    In order to know, over which dimension should a callback process be applied, reduce_dimension appends the
    reduction dimension to the reduce_by attribute of the data. The last element of this list is the current
    reduction dimension. This also allows multi-level reduce_dimension calls.

    https://processes.openeo.org/1.0.0/#array_element
    """

    def process(self, arguments):
        data = self.validate_parameter(arguments, "data", required=True, allowed_types=[xr.DataArray, list])
        index = self.validate_parameter(arguments, "index", required=False, allowed_types=[int], default=None)
        label = self.validate_parameter(arguments, "label", required=False, allowed_types=[float, str], default=None)
        return_nodata = self.validate_parameter(arguments, "return_nodata", default=False, allowed_types=[bool])

        if index is None and label is None:
            raise ProcessParameterInvalid(
                "array_element",
                "index/label",
                "The process 'array_element' requires either the 'index' or 'label' parameter to be set. (ArrayElementParameterMissing)",
            )
        if index is not None and label is not None:
            raise ProcessParameterInvalid(
                "array_element",
                "index/label",
                "The process 'array_element' only allows that either the 'index' or the 'label' parameter is set. (ArrayElementParameterConflict)",
            )

        if isinstance(data, xr.DataArray) and data.attrs and data.attrs.get("reduce_by"):
            dim = data.attrs.get("reduce_by")[-1]
            try:
                if index is not None:
                    result = data.isel({dim: index}, drop=True)
                    # mark the data - while it is still an xarray DataArray, the operations should now be applied to each element:
                    result.attrs["simulated_datatype"] = (float,)
                    return result
                else:
                    # Suprisingly this also works for the temporal dimension, when `label` is a string:
                    #   return data.sel({dim: label}, drop=True)
                    # Unfortunately, this approach doesn't work with Bands (when the label is an alias),
                    # so we must manually find the correct label index - which doesn't work with datetime:
                    all_coords = list(data.coords[dim].to_index())
                    if all_coords and isinstance(all_coords[0], datetime.datetime):
                        label_index = all_coords.index(parse_rfc3339(label))
                    else:
                        label_index = all_coords.index(label)
                    result = data.isel({dim: label_index}, drop=True)
                    # mark the data - while it is still an xarray DataArray, the operations should now be applied to each element:
                    result.attrs["simulated_datatype"] = (float,)
                    return result

            except (IndexError, KeyError, ValueError):
                if return_nodata:
                    """
                    According to documentation (https://open-eo.github.io/openeo-api/processreference/#array_element):
                        '''return_nodata: By default this process throws an IndexOutOfBounds exception if the index is invalid. If you want to return null instead, set this flag to true.'''
                    Thus, our understanding is that the array_element process should return a result of the same shape as a valid index would, but with all values set to null.
                    """
                    data_with_arbitrary_selection = data.isel({dim: 0}, drop=True)
                    return xr.full_like(data_with_arbitrary_selection, fill_value=np.nan, dtype=np.double)
                raise ProcessParameterInvalid(
                    "array_element",
                    "index/label",
                    "The array has no element with the specified index or label. (ArrayElementNotAvailable)",
                )
        else:
            try:
                return data[index]
            except IndexError:
                if return_nodata:
                    return None
                raise ProcessParameterInvalid(
                    "array_element",
                    "index/label",
                    "The array has no element with the specified index or label. (ArrayElementNotAvailable)",
                )
