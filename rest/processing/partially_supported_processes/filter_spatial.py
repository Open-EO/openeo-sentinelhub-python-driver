from shapely.geometry import shape

from processing.partially_supported_processes._partially_implemented_spatial_process import (
    PartiallyImplementedSpatialProcess,
)
from processing.utils import is_polygon_or_multi_polygon
from openeoerrors import UnsupportedGeometry


class FilterSpatial(PartiallyImplementedSpatialProcess):
    process_id = "filter_spatial"

    def __init__(self, process_graph):
        super().__init__(process_graph, FilterSpatial.process_id)

    def get_spatial_info(self):
        all_occurrences = self.get_all_occurrences_of_process_id(self.process_graph, self.process_id)

        if len(all_occurrences) == 0:
            return None, None

        final_geometry = None

        for occurrence in all_occurrences:
            geometries = self.process_graph[occurrence["node_id"]]["arguments"]["geometries"]

            if not is_polygon_or_multi_polygon(geometries):
                raise UnsupportedGeometry()

            if final_geometry is None:
                final_geometry = shape(geometries)
            else:
                final_geometry = final_geometry.intersection(shape(geometries))

        return final_geometry, None
