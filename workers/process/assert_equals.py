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
            # since it is important for us to know what the difference is, make
            # an effort to log both arguments nicely:
            indented_a = '    ' + str(a).replace('\n', '\n    ')
            indented_b = '    ' + str(b).replace('\n', '\n    ')
            message = f"""


**************************
***** ASSERT FAILED! *****
**************************

-----
Argument a:

{indented_a}

-----
Argument b:

{indented_b}

**************************

"""
            self.logger.info(message)
            raise ProcessArgumentInvalid(f"The argument 'b' in process 'assert_equals' is invalid: Parameters a and b differ (node: '{self.node_name}').")

        return None