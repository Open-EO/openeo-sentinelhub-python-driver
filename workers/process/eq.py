import numpy as np
import xarray as xr

xr.set_options(keep_attrs=True)

from ._common import ProcessEOTask, ProcessParameterInvalid, parse_rfc3339, DataCube


class eqEOTask(ProcessEOTask):
    """
    https://openeo.org/documentation/1.0/processes.html#eq
    """

    def process(self, arguments):
        x = self.validate_parameter(
            arguments, "x", required=True, allowed_types=[bool, float, str, dict, list, type(None)]
        )
        y = self.validate_parameter(
            arguments, "y", required=True, allowed_types=[bool, float, str, dict, list, type(None)]
        )
        delta = self.validate_parameter(
            arguments, "delta", required=False, default=None, allowed_types=[float, type(None)]
        )
        case_sensitive = self.validate_parameter(
            arguments, "case_sensitive", required=False, default=True, allowed_types=[bool]
        )

        if not isinstance(x, xr.DataArray) and not isinstance(y, xr.DataArray):
            if x is None or y is None:
                return None
            if isinstance(x, (list, dict)) or isinstance(y, (list, dict)):
                return False
            if type(x) != type(y):
                return False
            if isinstance(x, str):
                try:
                    x_datetime = parse_rfc3339(x)
                    y_datetime = parse_rfc3339(x)
                    return x_datetime == y_datetime
                except:
                    if case_sensitive:
                        return x == y
                    return x.lower() == y.lower()
            if isinstance(x, float):
                if delta is not None:
                    return abs(x - y) <= delta
                return x == y
            return False

        original_attrs = x.attrs if isinstance(x, xr.DataArray) else y.attrs
        # If the values are DataArrays, we assume they contain numbers
        if isinstance(x, xr.DataArray) and isinstance(y, xr.DataArray):
            if sorted(x.dims) == sorted(y.dims):
                y = y.transpose(*x.dims)
                if x.shape != y.shape:
                    raise ProcessParameterInvalid("eq", "x/y", "Cubes have different shapes.")
            else:
                raise ProcessParameterInvalid("eq", "x/y", "Cubes have different dimensions.")

            cube = x
            other_value = y
        else:
            if not isinstance(x, xr.DataArray):
                cube = y
                other_value = x
            else:
                cube = x
                other_value = y
            if isinstance(other_value, (list, dict)):
                result = DataCube.from_dataarray(xr.where(cube.isnull(), None, False))
                result.attrs = original_attrs
                return result
            other_value = DataCube(other_value)

        # Subtracting Nonetype is not possible, so we replace it with np.nan, which is a float
        cube = cube.fillna(np.nan)
        other_value = other_value.fillna(np.nan)

        if delta:
            m = np.abs(cube - other_value) <= delta
        else:
            m = cube == other_value

        result = DataCube.from_dataarray(xr.where(cube.isnull() + other_value.isnull(), None, m))
        result.attrs = original_attrs
        return result
