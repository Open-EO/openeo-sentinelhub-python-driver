from sentinelhub import ResamplingType

from processing.partially_supported_processes._partially_implemented_spatial_process import (
    PartiallyImplementedSpatialProcess,
)
from processing.utils import convert_projection_to_epsg_code
from openeoerrors import ProcessParameterInvalid


class ResampleSpatial(PartiallyImplementedSpatialProcess):
    process_id = "resample_spatial"

    def __init__(self, process_graph):
        super().__init__(process_graph, ResampleSpatial.process_id)

    def convert_resampling_method_to_sh(self, method):
        methods_mapping = {
            "near": ResamplingType.NEAREST,
            "bilinear": ResamplingType.BILINEAR,
            "cubic": ResamplingType.BICUBIC,
        }
        if method not in methods_mapping:
            raise ProcessParameterInvalid(
                "method",
                "resample_spatial",
                f"Method {method} not among supported resampling methods: ['near','bilinear','cubic']",
            )
        return methods_mapping[method]

    def validate_and_parse_resolution(self, resolution):
        if isinstance(resolution, (int, float)):
            return [resolution, resolution]
        elif isinstance(resolution, list):
            if len(resolution) == 2 and all(isinstance(x, (int, float)) for x in resolution):
                return resolution
        raise ProcessParameterInvalid(
            "resolution", "resample_spatial", "'resolution' must be number or array of 2 numbers."
        )

    def validate_and_parse_projection(self, projection):
        try:
            return convert_projection_to_epsg_code(projection)
        except:
            raise ProcessParameterInvalid(
                "projection",
                "resample_spatial",
                "'projection' is not a valid EPSG code, WKT string or PROJ definition.",
            )

    def get_spatial_info(self):
        all_occurrences = self.get_all_occurrences_ordered()

        if len(all_occurrences) == 0:
            return None, None, None, None

        final_resolution = None
        final_projection = None

        for occurrence in all_occurrences:
            resolution = self.process_graph[occurrence["node_id"]]["arguments"].get("resolution")
            projection = self.process_graph[occurrence["node_id"]]["arguments"].get("projection")

            if resolution is None and projection is None:
                raise ProcessParameterInvalid(
                    "resolution/projection",
                    "resample_spatial",
                    "At least 'resolution' or 'projection' must be specified.",
                )

            method = self.process_graph[occurrence["node_id"]]["arguments"].get("method", "near")
            method = self.convert_resampling_method_to_sh(method)

            if resolution is not None:
                final_resolution = self.validate_and_parse_resolution(resolution)
            if projection is not None:
                final_projection = self.validate_and_parse_projection(projection)

        return None, final_projection, final_resolution, method
