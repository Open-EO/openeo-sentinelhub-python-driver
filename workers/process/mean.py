import numpy as np
import xarray as xr
xr.set_options(keep_attrs=True)

from ._common import ProcessEOTask, ProcessArgumentInvalid, ProcessArgumentRequired

class meanEOTask(ProcessEOTask):
    def process(self, arguments):
        try:
            data = arguments["data"]
        except:
            raise ProcessArgumentRequired("Process 'reduce' requires argument 'data'.")

        ignore_nodata = arguments.get("ignore_nodata", True)

        if data.attrs and data.attrs.get("reduce_by"):
            axis = data.dims.index(data.attrs.get("reduce_by")[-1])
        else:
            axis = None

        if ignore_nodata:
            self.results = np.amin(data, axis=axis)
            print(">>>>>>>>>>>>>>>>>>>>>>> INTERMITTENT RESULTS:\n")
            print("Axis:",axis)
            print(self.results)
            print("\n<<<<<<<<<<<<<<<<<<<<<<<")
            return self.results
        else:
            try:
                self.results = np.nanmin(data, axis=axis)
                return self.results
            except ValueError:
                return None