import math

import numpy as np
import xarray as xr

xr.set_options(keep_attrs=True)

from ._common import ProcessEOTask, ProcessParameterInvalid, DataCube


class divideEOTask(ProcessEOTask):
    """
    This process is often used within reduce_dimension process, which could pass each of the vectors separately,
    but this would be very inefficient. Instead, we get passed a whole xarray with an attribute reduce_by.
    In order to know, over which dimension should a callback process be applied, reduce_dimension appends the
    reduction dimension to the reduce_by attribute of the data. The last element of this list is the current
    reduction dimension. This also allows multi-level reduce_dimension calls.
    """

    def process(self, arguments):
        x = self.validate_parameter(arguments, "x", required=True, allowed_types=[float, type(None)])
        y = self.validate_parameter(arguments, "y", required=True, allowed_types=[float, type(None)])

        # we might be passing the xr.DataArray and just simulating numbers, but let's take
        # care of "normal" use-case first:
        if not isinstance(x, xr.DataArray) and not isinstance(y, xr.DataArray):
            if x is None or y is None:
                return None
            if y == 0:
                return None if x == 0 else math.inf if x > 0 else -math.inf
            return x / y

        # at least one parameter is xr.DataArray
        original_attrs = x.attrs if isinstance(x, xr.DataArray) else y.attrs
        original_dim_types = x.get_dim_types() if isinstance(x, xr.DataArray) else y.get_dim_types()

        # we can't divide if one of the parameters is None:
        if x is None:
            # careful, dtype is mandatory or the results will be weird:
            x = DataCube.from_dataarray(xr.full_like(y, fill_value=np.nan, dtype=np.double))
        if y is None:
            y = DataCube.from_dataarray(xr.full_like(x, fill_value=np.nan, dtype=np.double))

        try:
            # xarray knows how to divide DataArrays and numbers in every combination:
            result = x / y
        except ValueError as ex:
            # non-matching dimensions could result in an exception:
            #   ValueError: arguments without labels along dimension '...' cannot be aligned because they have different dimension sizes: ...
            raise ProcessParameterInvalid("divide", "x/y", str(ex))
        result.attrs = original_attrs
        return DataCube.from_dataarray(result, original_dim_types)
