import re

import numpy as np
import xarray as xr

from ._common import ProcessEOTask, ProcessParameterInvalid, Band


class ndviEOTask(ProcessEOTask):
    def process(self, arguments):
        data = self.validate_parameter(arguments, "data", required=True, allowed_types=[xr.DataArray])
        nir = self.validate_parameter(arguments, "nir", required=False, allowed_types=[str], default="nir")
        red = self.validate_parameter(arguments, "red", required=False, allowed_types=[str], default="red")
        target_band = self.validate_parameter(
            arguments, "target_band", required=False, allowed_types=[str, type(None)], default=None
        )

        if "band" not in data.dims:
            raise ProcessParameterInvalid("ndvi", "data", "Dimension 'band' is missing (DimensionAmbiguous).")

        if target_band is not None:
            # "^\w+$" - \w is "from a-z, A-Z, 0-9, including the _ (underscore) character"
            if not re.match("^[A-Za-z0-9_]+$", target_band):
                raise ProcessParameterInvalid("ndvi", "target_band", "String does not match the required pattern.")
            # "If a band with the specified name exists, a BandExists is thrown."
            try:
                data.sel(band=target_band)
                raise ProcessParameterInvalid("ndvi", "target_band", "Band name already exists (BandExists).")
            except KeyError:
                pass

        try:
            nir_data = data.sel(band=nir)
        except KeyError:
            raise ProcessParameterInvalid("ndvi", "nir", "Parameter does not match any band (NirBandAmbiguous).")

        try:
            red_data = data.sel(band=red)
        except KeyError:
            raise ProcessParameterInvalid("ndvi", "red", "Parameter does not match any band (RedBandAmbiguous).")

        result = (nir_data - red_data) / (nir_data + red_data)

        if target_band is not None:
            # "By default, the dimension of type bands is dropped by this process. To keep the dimension
            # specify a new band name in the parameter target_band. This adds a new dimension label with
            # the specified name to the dimension, which can be used to access the computed values."
            r2 = result.expand_dims(dim="band")
            r3 = r2.assign_coords(band=[Band(target_band)])
            merged_result = xr.concat([data, r3], dim="band")
            return merged_result

        return result
