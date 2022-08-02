from shapely.geometry import shape

from processing.partially_supported_processes._partially_implemented_spatial_process import (
    PartiallyImplementedSpatialProcess,
)
from processing.utils import convert_extent_to_epsg4326, convert_extent_to_geojson


class FilterBBox(PartiallyImplementedSpatialProcess):
    process_id = "filter_bbox"

    def __init__(self, process_graph):
        super().__init__(process_graph, FilterBBox.process_id)

    def get_spatial_info(self):
        all_occurrences = self.get_all_occurrences_of_process_id(self.process_graph, self.process_id)

        if len(all_occurrences) == 0:
            return None, None, None, None

        last_occurrence_node_id = self.get_last_occurrence(all_occurrences)
        final_crs = self.process_graph[last_occurrence_node_id]["arguments"]["extent"].get("crs", 4326)
        final_geometry = None

        for occurrence in all_occurrences:
            extent = self.process_graph[occurrence["node_id"]]["arguments"]["extent"]
            extent = convert_extent_to_epsg4326(extent)
            extent_geojson = convert_extent_to_geojson(extent)
            polygon = shape(extent_geojson)

            if final_geometry is None:
                final_geometry = polygon
            else:
                final_geometry = final_geometry.intersection(polygon)
        return final_geometry, final_crs, None, None
