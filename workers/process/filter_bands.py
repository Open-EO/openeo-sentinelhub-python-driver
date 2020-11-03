import re

import numpy as np
import xarray as xr

from ._common import ProcessEOTask, ProcessParameterInvalid, Band


def get_bands_dims(data):
    """ Returns names of all the dimensions that represent bands """
    # this is not the correct way - dimension should know its type even if there are no coords in it
    result = [
        dim
        for dim in data.dims
        if dim in data.coords and len(data.coords) > 0 and isinstance(data.coords[dim].to_index()[0], Band)
    ]
    return result


class filter_bandsEOTask(ProcessEOTask):
    """ https://processes.openeo.org/1.0.0/#filter_bands """

    def process(self, arguments):
        data = self.validate_parameter(arguments, "data", required=True, allowed_types=[xr.DataArray])
        bands = self.validate_parameter(arguments, "bands", required=False, allowed_types=[list], default=[])
        wavelengths = self.validate_parameter(
            arguments, "wavelengths", required=False, allowed_types=[list], default=[]
        )

        bands_dims = get_bands_dims(data)
        # "The data cube is expected to have only one dimension of type bands."
        if len(bands_dims) > 1:
            raise ProcessParameterInvalid("filter_bands", "data", "Multiple dimensions of type 'bands' found.")
        # "Fails with a DimensionMissing error if no such dimension exists."
        if len(bands_dims) == 0:
            raise ProcessParameterInvalid(
                "filter_bands", "data", "No dimension of type 'bands' found (DimensionMissing)."
            )
        dim = bands_dims[0]

        # "If no criteria is specified, the BandFilterParameterMissing exception must be thrown."
        if len(bands) == 0 and len(wavelengths) == 0:
            raise ProcessParameterInvalid(
                "filter_bands",
                "bands/wavelengths",
                "One of the filtering parameters must be specified (BandFilterParameterMissing).",
            )

        # "Data type: array<band-name:string>"
        for b in bands:
            if not isinstance(b, str):
                raise ProcessParameterInvalid("filter_bands", "bands", "Band names must be strings.")
        # Data type: array<array<number>>
        for w in wavelengths:
            if not isinstance(w, list) or len(w) != 2:
                raise ProcessParameterInvalid(
                    "filter_bands", "bands", "Wavelengths must be lists with exactly 2 parameters."
                )
            try:
                if float(w[0]) > float(w[1]):
                    raise ProcessParameterInvalid(
                        "filter_bands",
                        "bands",
                        "First wavelength (min) must be lower or equal to the second one (max).",
                    )
            except (ValueError, TypeError):
                raise ProcessParameterInvalid("filter_bands", "bands", "Wavelength limits must be numbers.")

        # Note: information below is outdated (we no longer use MultiIndex), however, we still use `.where` instead
        # of `.sel` because it takes care of ordering the matching corrds correctly.
        #
        # We would use data.sel, but it drops a key from MultiIndex:
        #   >>> x
        #     <xarray.DataArray (b: 3)>
        #     array([3, 4, 5])
        #     Coordinates:
        #     * b           (b) MultiIndex
        #     - band        (b) object 'B01' 'B02' 'B03'
        #     - alias       (b) object nan 'nir' 'red'
        #     - wavelength  (b) float64 0.752 0.823 0.901
        #   >>> x.sel(b={"band": "B02"})
        #     <xarray.DataArray (b: 1)>
        #     array([4])
        #     Coordinates:
        #     * b           (b) MultiIndex
        #     - alias       (b) object 'nir'
        #     - wavelength  (b) float64 0.823
        #
        # Instead, data.where works, and it allows "OR" too:
        #   >>> x.where((x["b"]["band"]=="B02") | (x["b"]["band"]=="B03"), drop=True)
        #     <xarray.DataArray (b: 2)>
        #     array([4., 5.])
        #     Coordinates:
        #     * b           (b) MultiIndex
        #     - band        (b) object 'B02' 'B03'
        #     - alias       (b) object 'nir' 'red'
        #     - wavelength  (b) float64 0.823 0.901

        # make a copy of `data` but fill it with False values:
        already_included = xr.DataArray(False, dims=data.dims, coords=data.coords)
        result = None

        for b in bands:
            # xr.concat will duplicate existing coords, so we need to make sure in advance that we don't include duplicates:
            mask = (data[dim] == b) & np.logical_not(already_included)
            if not mask.any():
                continue

            # slice out the parts that conform to our mask:
            result_part = data.where(mask, drop=True)
            # merge them to the existing result:
            result = result_part if result is None else xr.concat([result, result_part], dim=dim)
            already_included = already_included | mask

        for w in wavelengths:
            # xr.concat will duplicate existing coords, so we need to make sure in advance that we don't include duplicates:
            mask = (data[dim] >= float(w[0])) & (data[dim] <= float(w[1])) & np.logical_not(already_included)
            if not mask.any():
                continue

            # slice out the parts that conform to our mask:
            result_part = data.where(mask, drop=True)
            # merge them to the existing result:
            result = result_part if result is None else xr.concat([result, result_part], dim=dim)
            already_included = already_included | mask

        if result is None:
            # keep the original shape, dims and coords, except for bands, where you remove all of them, but keep the dimension:
            all_bands = [x[0] for x in list(data.coords[dim].to_index())]
            return data.drop_sel({dim: all_bands})

        return result
