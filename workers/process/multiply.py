import numpy as np

from ._common import ProcessEOTask, ProcessParameterInvalid, DataCube


class multiplyEOTask(ProcessEOTask):
    def process(self, arguments):
        x = self.validate_parameter(arguments, "x", required=True, allowed_types=[float, type(None)])
        y = self.validate_parameter(arguments, "y", required=True, allowed_types=[float, type(None)])

        # we might be passing the DataCube and just simulating numbers, but let's take
        # care of "normal" use-case first:
        if not isinstance(x, DataCube) and not isinstance(y, DataCube):
            if x is None or y is None:
                return None
            return x * y

        # at least one parameter is DataCube
        original_attrs = x.attrs if isinstance(x, DataCube) else y.attrs
        original_dim_types = x.get_dim_types() if isinstance(x, DataCube) else y.get_dim_types()

        # we can't multiply if one of the parameters is None:
        if x is None:
            x = DataCube.full_like(y, fill_value=np.nan, dtype=np.double)
        if y is None:
            y = DataCube.full_like(x, fill_value=np.nan, dtype=np.double)

        try:
            # xarray knows how to multiply DataArrays and numbers in every combination:
            result = x * y
        except ValueError as ex:
            # non-matching dimensions could result in an exception:
            #   ValueError: arguments without labels along dimension '...' cannot be aligned because they have different dimension sizes: ...
            raise ProcessParameterInvalid("multiply", "x/y", str(ex))

        result.attrs = original_attrs
        # Once we get rid of "reduce_by", we can forget origianl attrs and be more explicit:
        #  # the result is always a number:
        #  result.attrs["simulated_datatype"] = (float,)
        return DataCube.from_dataarray(result, original_dim_types)
