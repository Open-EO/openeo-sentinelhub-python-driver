import numpy as np
import xarray as xr
import math

from ._common import ProcessEOTask, ProcessParameterInvalid


class linear_scale_rangeEOTask(ProcessEOTask):
    """
    This process is often used within apply process. Apply could pass each of the values separately,
    but this would be very inefficient. Instead, we get passed a whole xarray, which is the reason
    why we allow `xr.DataArray` as "data" parameter type.
    """

    def process(self, arguments):
        data = self.validate_parameter(arguments, "x", required=True, allowed_types=[float, type(None)])
        inputMin = self.validate_parameter(arguments, "inputMin", required=True, allowed_types=[float])
        inputMax = self.validate_parameter(arguments, "inputMax", required=True, allowed_types=[float])
        outputMin = self.validate_parameter(arguments, "outputMin", default=0, allowed_types=[float])
        outputMax = self.validate_parameter(arguments, "outputMax", default=1, allowed_types=[float])

        if data is None:
            return None

        if math.isclose(inputMin, inputMax):
            raise ProcessParameterInvalid(
                "linear_scale_range", "inputMin", "Argument must differ from argument 'inputMax'."
            )

        original_type_was_number, data = self.convert_to_datacube(data)

        if data.size == 0:
            return None

        results = ((data - inputMin) / (inputMax - inputMin)) * (outputMax - outputMin) + outputMin

        if original_type_was_number:
            return float(results)

        if isinstance(results, xr.DataArray):
            results.attrs["simulated_datatype"] = (float,)

        return results
