import datetime
import math

import numpy as np
import xarray as xr

from ._common import ProcessEOTask, DATA_TYPE_TEMPORAL_INTERVAL, ProcessParameterInvalid, DimensionType, DataCube


class filter_temporalEOTask(ProcessEOTask):
    """
    https://processes.openeo.org/#filter_temporal
    """

    def process(self, arguments):
        data = self.validate_parameter(arguments, "data", required=True, allowed_types=[xr.DataArray])
        extent_from, extent_to = self.validate_parameter(
            arguments, "extent", required=True, allowed_types=[DATA_TYPE_TEMPORAL_INTERVAL]
        )
        dimension = self.validate_parameter(
            arguments, "dimension", required=False, allowed_types=[str, type(None)], default=None
        )

        if dimension is None:
            # "If the dimension is set to null (it's the default value), the data cube is expected to only have one temporal dimension."
            # "If the dimension is not set or is set to null, the filter applies to all temporal dimensions."
            # "Fails with a DimensionNotAvailable error if the specified dimension does not exist."
            temporal_dims = data.get_dims_of_type(DimensionType.TEMPORAL)
            # There should be exactly one temporal dimension:
            if len(temporal_dims) > 1:
                raise ProcessParameterInvalid(
                    "filter_temporal",
                    "dimension",
                    "More than one temporal dimension available, please specify dimension.",
                )
            if len(temporal_dims) == 0:
                raise ProcessParameterInvalid("filter_temporal", "dimension", "No temporal dimension is available.")
            dimension = temporal_dims[0]
        else:
            if dimension not in data.dims:
                raise ProcessParameterInvalid(
                    "filter_temporal", "dimension", "A dimension with the specified name does not exist."
                )
            if data.get_dim_type(dimension) != DimensionType.TEMPORAL:
                raise ProcessParameterInvalid(
                    "filter_temporal", "dimension", "A dimension with the specified name is not temporal."
                )

        # make sure that upper limit is excluded - subtract a millisecond:
        if extent_to is not None:
            extent_to = extent_to - datetime.timedelta(milliseconds=1)

        result = data.loc[{dimension: slice(extent_from, extent_to)}]
        return result
