from processing.partially_supported_processes._partially_implemented_spatial_process import (
    PartiallyImplementedSpatialProcess,
)


class FilterBBox(PartiallyImplementedSpatialProcess):
    def __init__(self, process_graph):
        super().__init__(process_graph, "filter_bbox")
