import numpy as np
import xarray as xr
import math

from ._common import ProcessEOTask, ProcessArgumentInvalid, ProcessArgumentRequired

class linear_scale_rangeEOTask(ProcessEOTask):
    """
        This process is often used within apply process. Apply could pass each of the values separately, 
        but this would be very inefficient. Instead, we get passed a whole xarray.
    """
    def process(self, arguments):
        data = self.validate_parameter(arguments, "x", required=True, allowed_types=[xr.DataArray, int, float, type(None)])
        inputMin = self.validate_parameter(arguments, "inputMin", required=True, allowed_types=[int, float])
        inputMax = self.validate_parameter(arguments, "inputMax", required=True, allowed_types=[int, float])
        outputMin = self.validate_parameter(arguments, "outputMin", default=0, allowed_types=[int, float])
        outputMax = self.validate_parameter(arguments, "outputMax", default=1, allowed_types=[int, float])

        if data is None:
            return None

        if math.isclose(inputMin,inputMax):
            raise ProcessArgumentInvalid("The argument 'inputMin' in process 'linear_scale_range' is invalid: Argument must differ from argument 'inputMax'.")

        original_type_was_number, data = self.convert_to_dataarray(data)

        if data.size == 0:
            return None

        results = ((data - inputMin) / (inputMax - inputMin)) * (outputMax - outputMin) + outputMin

        if original_type_was_number:
            return float(results)

        return results