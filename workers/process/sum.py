import numpy as np
import xarray as xr
xr.set_options(keep_attrs=True)

from ._common import ProcessEOTask, ProcessArgumentInvalid, ProcessArgumentRequired

class sumEOTask(ProcessEOTask):
    def process(self, arguments):
        try:
            data = arguments["data"]
        except:
            raise ProcessArgumentRequired("Process 'reduce' requires argument 'data'.")

        ignore_nodata = arguments.get("ignore_nodata", True)

        if not isinstance(ignore_nodata, bool):
            raise ProcessArgumentInvalid("The argument 'ignore_nodata' in process 'sum' is invalid: Argument must be of type 'boolean'.")

        dim, changed_type = None, False

        if len(data) < 2:
            raise ProcessArgumentInvalid("The argument 'data' in process 'sum' is invalid: Array must have at least 2 elements.")

        for i,element in enumerate(data):
            if not isinstance(element, xr.DataArray):
                changed_type = True
                data[i] = xr.DataArray(np.array(element, dtype=np.float))

        summation_array = xr.concat(data, dim="temporary_summation_dim")
        self.results = summation_array.sum(dim="temporary_summation_dim", skipna=ignore_nodata, keep_attrs=True)

        if self.results.size == 1 and changed_type:
            if np.isnan(self.results):
                return None
            else:
                return float(self.results)

        return self.results

