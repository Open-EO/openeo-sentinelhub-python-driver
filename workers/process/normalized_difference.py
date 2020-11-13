import re

import numpy as np
import xarray as xr

from ._common import ProcessEOTask, ProcessParameterInvalid, Band, DataCube


class normalized_differenceEOTask(ProcessEOTask):
    def process(self, arguments):
        x = self.validate_parameter(arguments, "x", required=True, allowed_types=[float, type(None)])
        y = self.validate_parameter(arguments, "y", required=True, allowed_types=[float, type(None)])

        # we might be passing the xr.DataArray and just simulating numbers, but let's take
        # care of "normal" use-case first:
        if not isinstance(x, xr.DataArray) and not isinstance(y, xr.DataArray):
            if x is None or y is None:
                return None
            try:
                return (x - y) / (x + y)
            except ZeroDivisionError:
                return None

        # at least one parameter is xr.DataArray
        original_attrs = x.attrs if isinstance(x, xr.DataArray) else y.attrs
        original_dim_types = x.get_dim_types() if isinstance(x, xr.DataArray) else y.get_dim_types()

        # we can't normalized_difference if one of the parameters is None:
        if x is None:
            x = xr.full_like(y, fill_value=np.nan, dtype=np.double)
        if y is None:
            y = xr.full_like(x, fill_value=np.nan, dtype=np.double)

        try:
            # xarray knows how to normalized_difference DataArrays and numbers in every combination:
            result = (x - y) / (x + y)
        except ValueError as ex:
            # non-matching dimensions could result in an exception:
            #   ValueError: arguments without labels along dimension '...' cannot be aligned because they have different dimension sizes: ...
            raise ProcessParameterInvalid("normalized_difference", "x/y", str(ex))

        result.attrs = original_attrs
        # Once we get rid of "reduce_by", we can forget origianl attrs and be more explicit:
        #  # the result is always a number:
        #  result.attrs["simulated_datatype"] = (float,)
        return DataCube.from_dataarray(result, original_dim_types)
