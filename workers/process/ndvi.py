from ._common import ProcessEOTask, ProcessArgumentInvalid, ProcessArgumentRequired
import xarray as xr
import re

xr.set_options(keep_attrs=True)


class ndviEOTask(ProcessEOTask):
    def process(self, arguments):
        data = self.validate_parameter(arguments, "data", required=True, allowed_types=[xr.DataArray])
        name = self.validate_parameter(arguments, "name", default="ndvi", allowed_types=[str])
        if not re.match("^[A-Za-z0-9_]+$", name):
            raise ProcessArgumentInvalid(
                "The argument 'name' in process 'ndvi' is invalid: string does not match the required pattern."
            )

        nir_band = data.attrs["band_aliases"].get("nir", "nir")
        red_band = data.attrs["band_aliases"].get("red", "red")

        nir = data.where(data.band == nir_band, drop=True)
        red = data.where(data.band == red_band, drop=True)

        nir.coords["band"] = [name]
        red.coords["band"] = [name]

        result = (nir - red) / (nir + red)

        return result
