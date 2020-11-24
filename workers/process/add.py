import numpy as np
import xarray as xr

xr.set_options(keep_attrs=True)
from ._common import ProcessEOTask, ProcessParameterInvalid, DataCube


class addEOTask(ProcessEOTask):
    def process(self, arguments):
        x = self.validate_parameter(arguments, "x", required=True, allowed_types=[float, type(None)])
        y = self.validate_parameter(arguments, "y", required=True, allowed_types=[float, type(None)])
        # null is returned if any element is such a value:
        if not isinstance(x, xr.DataArray) and not isinstance(y, xr.DataArray):
            if x is None or y is None:
                return None
            return x + y

        # at least one parameter is xr.DataArray
        original_attrs = x.attrs if isinstance(x, xr.DataArray) else y.attrs
        original_dim_types = x.get_dim_types() if isinstance(x, xr.DataArray) else y.get_dim_types()

        # we can't subtract if one of the parameters is None:
        if x is None:
            # careful, dtype is mandatory or the results will be weird:
            x = DataCube.full_like(y, fill_value=np.nan, dtype=np.double)
        if y is None:
            y = DataCube.full_like(x, fill_value=np.nan, dtype=np.double)

        try:
            result = x + y
        except ValueError as ex:
            # non-matching dimensions could result in an exception:
            #   ValueError: arguments without labels along dimension '...' cannot be aligned because they have different dimension sizes: ...
            raise ProcessParameterInvalid("add", "x/y", str(ex))
        result.attrs = original_attrs
        return DataCube.from_dataarray(result, original_dim_types)
