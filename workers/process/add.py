from ._common import ProcessEOTask,ProcessParameterInvalid


class addEOTask(ProcessEOTask):

    def process(self, arguments):
        x = self.validate_parameter(arguments, "x", required=True, allowed_types=[float, type(None)])
        y = self.validate_parameter(arguments, "y", required=True, allowed_types=[float, type(None)])
        # null is returned if any element is such a value:
        if x is None or y is None:
            return None

        try:
            result = x + y
        except ValueError as ex:
            # non-matching dimensions could result in an exception:
            raise ProcessParameterInvalid("add", "x+y", str(ex))
        return result
