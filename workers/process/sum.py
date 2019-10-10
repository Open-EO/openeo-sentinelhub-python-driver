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

        # if data.attrs and data.attrs.get("reduce_by"):
        #     axis = data.dims.index(data.attrs.get("reduce_by")[-1])
        # else:
        #     axis = None

        self.results = xr.DataArray(data, attrs=data[0].attrs).sum(axis=0, skipna=ignore_nodata, keep_attrs=True)
        return self.results

        # if ignore_nodata:
        #     self.results = np.sum(data, axis=0)
        #     print(">>>>>>>>>>>>>>>>>>>>>>> INTERMITTENT RESULTS:\n")
        #     # print("Axis:",axis)
        #     print(self.results)
        #     print("\n<<<<<<<<<<<<<<<<<<<<<<<")
        #     return self.results
        # else:
        #     try:
        #         self.results = np.nansum(data, axis=0)
        #         return self.results
        #     except ValueError:
        #         return None
