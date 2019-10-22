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
        required_arguments = ["x", "inputMin", "inputMax"]

        for required_argument in required_arguments:
            try:
                data = arguments[required_argument]
            except:
                raise ProcessArgumentRequired("Process 'linear_scale_range' requires argument '{}'.".format(required_argument))

        number_arguments = ["inputMin","inputMax","outputMin","outputMax"]
        for number_argument in number_arguments:
            argument_value = arguments.get(number_argument)
            if argument_value:
                if not isinstance(argument_value, (int,float)):
                    raise ProcessArgumentInvalid("The argument '{}' in process 'linear_scale_range' is invalid: Argument must be of type 'number'.".format(number_argument))

        data, inputMin, inputMax = arguments["x"], arguments["inputMin"], arguments["inputMax"]
        outputMin, outputMax = arguments.get("outputMin",0), arguments.get("outputMax",1)

        if data is None:
            return None

        if math.isclose(inputMin,inputMax):
            raise ProcessArgumentInvalid("The argument 'inputMin' in process 'linear_scale_range' is invalid: Argument must differ from argument 'inputMax'.")

        original_type_was_number = False

        if not isinstance(data, xr.DataArray):
            if not isinstance(data, (int,float)):
                raise ProcessArgumentInvalid("The argument 'x' in process 'linear_scale_range' is invalid: Argument must be of type 'number' or 'null'.")

            original_type_was_number = True
            data = xr.DataArray(np.array(data, dtype=np.float))

            if data.size == 0:
                return None

        results = ((data - inputMin) / (inputMax - inputMin)) * (outputMax - outputMin) + outputMin

        if original_type_was_number:
            return float(results)

        return results