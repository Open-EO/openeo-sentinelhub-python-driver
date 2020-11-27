from ._common import ProcessEOTask, ProcessParameterInvalid, DataCube, assert_equal


class assert_equalsEOTask(ProcessEOTask):
    """
    Compares parameters a and b and throws error if they differ (beyond some tolerance).
    """

    def process(self, arguments):
        a = self.validate_parameter(arguments, "a", required=True, allowed_types=[DataCube])
        b = self.validate_parameter(arguments, "b", required=True, allowed_types=[DataCube])

        if "simulated_datatype" in a.attrs and a.attrs["simulated_datatype"] is None:
            del a.attrs["simulated_datatype"]
        if "simulated_datatype" in b.attrs and b.attrs["simulated_datatype"] is None:
            del b.attrs["simulated_datatype"]

        try:
            assert_equal(a, b)
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
