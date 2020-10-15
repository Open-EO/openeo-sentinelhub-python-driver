import numpy as np
import xarray as xr
import math
from datetime import datetime
from sentinelhub import CRS, BBox

from ._common import ProcessEOTask


class create_cubeEOTask(ProcessEOTask):
    """
    This process generates an xarray from input data. It is useful for writing tests, because
    it allows us to generate synthetic data, which we can then process and compare to expected
    (again synthetic) result.
    """

    def process(self, arguments):
        data_as_list = self.validate_parameter(arguments, "data", required=True, allowed_types=[list])
        dims = self.validate_parameter(arguments, "dims", required=True, allowed_types=[list])
        coords = self.validate_parameter(arguments, "coords", allowed_types=[dict], default={})

        if "t" in coords:
            coords["t"] = [datetime.strptime(d, "%Y-%m-%d %H:%M:%S") for d in coords["t"]]

        data = xr.DataArray(
            np.array(data_as_list, dtype=np.float),
            coords=coords,
            dims=dims,
            attrs={
                "band_aliases": {},
                "bbox": BBox(
                    (
                        12.0,
                        45.0,
                        13.0,
                        46.0,
                    ),
                    CRS(4326),
                ),
            },
        )
        self.logger.info(data)
        return data
