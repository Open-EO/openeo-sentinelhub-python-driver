import xarray as xr
from xarray.testing import assert_allclose

from ._common import ProcessEOTask, ProcessArgumentInvalid, ProcessArgumentRequired

class assert_equalsEOTask(ProcessEOTask):
    """
        Compares parameters a and b and throws error if they differ (beyond some tolerance).
    """
    def process(self, arguments):
        a = self.validate_parameter(arguments, "a", required=True, allowed_types=[xr.DataArray])
        b = self.validate_parameter(arguments, "b", required=True, allowed_types=[xr.DataArray])

        try:
            assert_allclose(a, b)
        except:
            raise ProcessArgumentInvalid(f"The argument 'b' in process 'assert_equals' is invalid: Parameters a and b differ (node: '{self.node_name}').")

        return None