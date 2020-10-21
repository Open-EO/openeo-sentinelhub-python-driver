from datetime import datetime
import math

import numpy as np
import pandas as pd
import xarray as xr
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

        if "band" in coords:
            bands = coords["band"][0]
            aliases = coords["band"][1]
            wavelenghts = coords["band"][2]
            coords["band"] = pd.MultiIndex.from_arrays(
                [bands, aliases, wavelenghts], names=("_name", "_alias", "_wavelength")
            )

        try:
            data = xr.DataArray(
                np.array(data_as_list, dtype=np.float),
                coords=coords,
                dims=dims,
                attrs={
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
        except:
            # if exception happens, log the parameters for easier debugging:
            self.logger.exception("Creating raster-cube failed, parameters were:")
            self.logger.info(f"    data_as_list: {repr(data_as_list)}")
            self.logger.info(f"    dims: {repr(dims)}")
            self.logger.info(f"    coords: {repr(coords)}")
            raise

        self.logger.info(data)
        return data
