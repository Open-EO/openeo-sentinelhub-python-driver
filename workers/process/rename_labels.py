import datetime
import math

import numpy as np
import xarray as xr

from ._common import ProcessEOTask, DATA_TYPE_TEMPORAL_INTERVAL, ProcessParameterInvalid


class rename_labelsEOTask(ProcessEOTask):
    """
    https://processes.openeo.org/#rename_labels
    """

    def process(self, arguments):
        data = self.validate_parameter(arguments, "data", required=True, allowed_types=[xr.DataArray])
        dimension = self.validate_parameter(arguments, "dimension", required=True, allowed_types=[str])
        target = self.validate_parameter(arguments, "target", required=True, allowed_types=[list])
        source = self.validate_parameter(arguments, "source", required=False, allowed_types=[list], default=[])

        if dimension not in data.dims:
            raise ProcessParameterInvalid(
                "rename_labels", "dimension", "A dimension with the specified name does not exist."
            )

        # "By default, the array is empty so that the dimension labels in the data cube are expected to be enumerated."
        must_be_enumerated = False
        if len(source) == 0:
            source = range(len(target))
            must_be_enumerated = True

        if len(source) != len(target):
            raise ProcessParameterInvalid(
                "rename_labels", "source/target", "Size of source and target does not match (LabelMismatch)."
            )

        # "If one of the source dimension labels doesn't exist, a LabelNotAvailable error is thrown."
        for s in source:
            if not s in data.coords[dimension]:
                if must_be_enumerated:
                    raise ProcessParameterInvalid(
                        "rename_labels",
                        "source",
                        "With source not supplied, data labels must be enumerated (LabelsNotEnumerated).",
                    )
                else:
                    raise ProcessParameterInvalid(
                        "rename_labels",
                        "source",
                        "Source label / enumeration index does not exist (LabelNotAvailable).",
                    )

        # "If a target dimension label already exists in the data cube, a LabelExists error is thrown."
        for t in target:
            if t in data.coords[dimension]:
                raise ProcessParameterInvalid("rename_labels", "target", "Target label already exists (LabelExists).")

        # replace the coords using source -> target mapping:
        coords = list(data.coords["x"].to_index())
        for s, t in zip(source, target):
            index = coords.index(s)
            coords[index] = t

        result = data.copy(deep=False)
        result.coords[dimension] = coords
        return result
