import xarray as xr
from xarray.testing import assert_allclose, assert_equal

from ._common import ProcessEOTask, ProcessParameterInvalid


class assert_equalsEOTask(ProcessEOTask):
    """
    Compares parameters a and b and throws error if they differ (beyond some tolerance).
    """

    def process(self, arguments):
        a = self.validate_parameter(arguments, "a", required=True, allowed_types=[xr.DataArray])
        b = self.validate_parameter(arguments, "b", required=True, allowed_types=[xr.DataArray])

        if "simulated_datatype" in a.attrs and a.attrs["simulated_datatype"] is None:
            del a.attrs["simulated_datatype"]
        if "simulated_datatype" in b.attrs and b.attrs["simulated_datatype"] is None:
            del b.attrs["simulated_datatype"]

        try:
            # When comparing DataArrays with MultiIndex dimension(s) (e.g. "band"), assert_allclose
            # fails. We still need it to make sure we don't trip over "almost equal" values:
            assert_equal(a, b)
        except AssertionError:
            try:
                assert_allclose(a, b)
            except:
                # since it is important for us to know what the difference is, make
                # an effort to log both arguments nicely:
                indented_a = "    " + str(a).replace("\n", "\n    ")
                indented_b = "    " + str(b).replace("\n", "\n    ")
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
            raise ProcessParameterInvalid(
                "assert_equals",
                "b",
                f"Parameters a and b differ (node: '{self.node_name}').",
            )

        return None
