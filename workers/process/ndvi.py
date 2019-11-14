from ._common import ProcessEOTask, ProcessArgumentInvalid, ProcessArgumentRequired
import xarray as xr
import re

class ndviEOTask(ProcessEOTask):
    def process(self, arguments):
        data = self.validate_parameter(arguments, "data", required=True, allowed_types=[xr.DataArray])
        name = self.validate_parameter(arguments, "name", default="ndvi", allowed_types=[str])
        if not re.match("^[A-Za-z0-9_]+$", name):
            raise ProcessArgumentInvalid("The argument 'name' in process 'ndvi' is invalid: string does not match the required pattern.")

        nir_band = data.attrs["band_aliases"].get("nir", "nir")
        red_band = data.attrs["band_aliases"].get("red", "red")

        nir = data.sel(band=nir_band)
        red = data.sel(band=red_band)

        result = (nir - red) / (nir + red)

        # result now has only 3 dimensions (dimension 'band' was lost), so we
        # need to add the missing dimension back:
        result = result.expand_dims('band')
        result = result.assign_coords(band=[name])
        # pass the spatial extent along:
        result = result.assign_attrs({
            "bbox": data.attrs["bbox"],
        })

        return result
