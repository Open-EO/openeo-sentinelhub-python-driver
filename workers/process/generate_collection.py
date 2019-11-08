import numpy as np
import xarray as xr
import math

from ._common import ProcessEOTask, ProcessArgumentInvalid, ProcessArgumentRequired

class generate_collectionEOTask(ProcessEOTask):
    """
        This process generates an xarray from input data. It is useful for writing tests, because
        it allows us to generate synthetic data, which we can then process and compare to expected
        (again synthetic) result.
    """
    def process(self, arguments):
        data_as_list = self.validate_parameter(arguments, "data", required=True, allowed_types=[list])
        dims = self.validate_parameter(arguments, "dims", required=True, allowed_types=[list])
        coords = self.validate_parameter(arguments, "coords", required=True, allowed_types=[dict])

        data = xr.DataArray(data_as_list, coords=coords, dims=dims)
        self.logger.info(data)
        return data