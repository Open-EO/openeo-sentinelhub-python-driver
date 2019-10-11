import numpy as np
import xarray as xr

from ._common import ProcessEOTask, ProcessArgumentInvalid, ProcessArgumentRequired

class meanEOTask(ProcessEOTask):
    def process(self, arguments):
        try:
            data = arguments["data"]
        except:
            raise ProcessArgumentRequired("Process 'mean' requires argument 'data'.")

        ignore_nodata = arguments.get("ignore_nodata", True)

        if not isinstance(ignore_nodata, bool):
            raise ProcessArgumentInvalid("The argument 'ignore_nodata' in process 'mean' is invalid: Argument must be of type 'boolean'.")

        dim, changed_type = None, False

        if not isinstance(data, xr.DataArray):
            changed_type = True
            data = xr.DataArray(np.array(data, dtype=np.float))

            if data.size == 0:
                return None

        if data.attrs and data.attrs.get("reduce_by"):
            dim = data.attrs.get("reduce_by")[-1]

        self.results = data.mean(dim=dim, skipna=ignore_nodata, keep_attrs=True)

        if self.results.size == 1 and changed_type:
            if np.isnan(self.results):
                return None
            return float(self.results)

        return self.results