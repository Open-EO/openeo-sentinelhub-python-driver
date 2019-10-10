import numpy as np

from ._common import ProcessEOTask, ProcessArgumentInvalid, ProcessArgumentRequired
import process

class minEOTask(ProcessEOTask):
    def process(self, arguments):
        try:
            data = arguments["data"]
        except:
            raise ProcessArgumentRequired("Process 'reduce' requires argument 'data'.")

        ignore_nodata = arguments.get("ignore_nodata", True)

        if hasattr(self, 'dimension'):
            axis = data.dims.index(self.dimension)
        else:
            axis = None

        if ignore_nodata:
            self.results = np.amin(data, axis=axis)
            return self.results
        else:
            try:
                self.results = np.nanmin(data, axis=axis)
                return self.results
            except ValueError:
                return None
