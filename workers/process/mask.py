import numpy as np
import xarray as xr

xr.set_options(keep_attrs=True)

from ._common import ProcessEOTask, ProcessParameterInvalid


class maskEOTask(ProcessEOTask):
    """
    https://processes.openeo.org/1.0.0/#mask
    """

    def process(self, arguments):
        data = self.validate_parameter(arguments, "data", required=True, allowed_types=[xr.DataArray])
        mask = self.validate_parameter(arguments, "mask", required=True, allowed_types=[xr.DataArray])
        replacement = self.validate_parameter(
            arguments, "replacement", required=False, default=np.nan, allowed_types=[float, bool, str, type(None)]
        )
        common_dims = set(data.dims).intersection(set(mask.dims))
        if not (common_dims == set(mask.dims)):
            raise ProcessParameterInvalid("mask", "data/mask", "Some dimensions in mask are not available in data.")
        try:
            return data.where(mask, other=replacement)
        except:
            raise ProcessParameterInvalid("mask", "data/mask", "Data and mask have different labels")
