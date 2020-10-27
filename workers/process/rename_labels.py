import datetime
import math

import numpy as np
import pandas as pd
import xarray as xr

from ._common import ProcessEOTask, DATA_TYPE_TEMPORAL_INTERVAL, ProcessParameterInvalid


class rename_labelsEOTask(ProcessEOTask):
    """
    https://processes.openeo.org/1.0.0/#rename_labels
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

        # Unfortunately, bands coordinates behave differently from other coords, so we need to detect if we are dealing with them:
        dim_is_bands = isinstance(data.coords[dimension].to_index(), pd.MultiIndex)

        # "If one of the source dimension labels doesn't exist, a LabelNotAvailable error is thrown."
        for s in source:
            s_exists = data.coords[dimension].sel({dimension: s}) if dim_is_bands else s in data.coords[dimension]
            if not s_exists:
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

        # make replacements of coords using source -> target mapping:
        target_coords = None
        if dim_is_bands:
            src_coords = list(data.coords[dimension].to_index())
            bands = [x[0] for x in src_coords]
            aliases = [x[1] for x in src_coords]
            wavelengths = [x[2] for x in src_coords]
            for s, t in zip(source, target):
                s_index = [i for i, x in enumerate(src_coords) if x[0] == s or x[1] == s][0]
                bands[s_index] = t
                aliases[s_index] = None
                wavelengths[s_index] = None
            target_coords = pd.MultiIndex.from_arrays(
                [bands, aliases, wavelengths], names=("_name", "_alias", "_wavelength")
            )
        else:
            target_coords = list(data.coords[dimension].to_index())
            for s, t in zip(source, target):
                index = target_coords.index(s)
                target_coords[index] = t

        result = data.copy(deep=False)
        result.coords[dimension] = target_coords
        return result
