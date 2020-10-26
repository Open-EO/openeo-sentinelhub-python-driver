import numpy as np
import xarray as xr

xr.set_options(keep_attrs=True)

from ._common import ProcessEOTask, ProcessParameterInvalid


class subtractEOTask(ProcessEOTask):
    """
    https://processes.openeo.org/1.0.0/#subtract
    """

    def process(self, arguments):
        x = self.validate_parameter(arguments, "x", required=True, allowed_types=[float, type(None)])
        y = self.validate_parameter(arguments, "y", required=True, allowed_types=[float, type(None)])

        # we might be passing the xr.DataArray and just simulating numbers, but let's take
        # care of "normal" use-case first:
        if not isinstance(x, xr.DataArray) and not isinstance(y, xr.DataArray):
            if x is None or y is None:
                return None
            return x - y

        # at least one parameter is xr.DataArray
        original_attrs = x.attrs if isinstance(x, xr.DataArray) else y.attrs

        # we can't subtract if one of the parameters is None:
        if x is None:
            # careful, dtype is mandatory or the results will be weird:
            x = xr.full_like(y, fill_value=np.nan, dtype=np.double)
        if y is None:
            y = xr.full_like(x, fill_value=np.nan, dtype=np.double)

        try:
            result = x - y
        except ValueError as ex:
            # non-matching dimensions could result in an exception:
            #   ValueError: arguments without labels along dimension '...' cannot be aligned because they have different dimension sizes: ...
            raise ProcessParameterInvalid("subtract", "x/y", str(ex))
        result.attrs = original_attrs
        return result
