from pyproj import CRS, Transformer
from pg_to_evalscript.process_graph_utils import get_dependencies, get_dependents, get_execution_order

from openeoerrors import PartiallySupportedProcessInvalid


class PartiallyImplementedSpatialProcess:
    def __init__(self, process_graph, process_id):
        self.process_id = process_id
        self.process_graph = process_graph
        self.dependencies = get_dependencies(process_graph)
        self.dependents = get_dependents(self.dependencies)
        self.execution_order = get_execution_order(self.dependencies, self.dependents)

    def get_all_occurrences(self):
        return self.get_all_occurrences_of_process_id(self.process_graph, self.process_id)

    def get_all_occurrences_ordered(self):
        all_occurrences = self.get_all_occurrences_of_process_id(self.process_graph, self.process_id)
        for occurrence in all_occurrences:
            occurrence["index"] = self.execution_order.index(occurrence["node_id"])
        all_occurrences.sort(key=lambda x: x["index"])
        return all_occurrences

    def get_all_occurrences_of_process_id(self, process_graph, process_id, level=0, all_occurrences=None):
        """
        Iterates over the process graph to find all nodes with `process_id` process.
        Returns the list of node ids and nesting levels of occurrences.
        """
        if all_occurrences is None:
            all_occurrences = []

        for node_id, node in process_graph.items():
            if node["process_id"] == process_id:
                all_occurrences.append({"node_id": node_id, "level": level})
                continue
            for arg_name, arg_val in node["arguments"].items():
                if isinstance(arg_val, dict) and "process_graph" in arg_val:
                    self.get_all_occurrences_of_process_id(
                        arg_val["process_graph"], process_id, level=level + 1, all_occurrences=all_occurrences
                    )
        return all_occurrences

    def is_usage_valid(self):
        """
        Partially implemented spatial processes are only valid if:
          - are not used inside other processes
          - are in the main processing chain (not e.g. in just one branch, that then joins into the main processing branch)
        Returns is_valid (bool) and a associated error object if is_valid is False.
        """
        all_occurrences = self.get_all_occurrences_of_process_id(self.process_graph, self.process_id)

        for occurrence in all_occurrences:
            if occurrence["level"] > 0:
                return False, PartiallySupportedProcessInvalid(
                    self.process_id,
                    "Process cannot be used in processes inside other processes.",
                )

            index_of_node = self.execution_order.index(occurrence["node_id"])
            descendants = self.execution_order[index_of_node + 1 :]

            if not self.check_if_node_common_ancestor(occurrence["node_id"], descendants):
                return False, PartiallySupportedProcessInvalid(
                    self.process_id, "Process must be part of the main processing chain."
                )

        return True, None

    def check_if_node_common_ancestor(self, node_id, descendants):
        """
        Checks every node in descendants has a common only ancestor node_id
        """
        for descendant in descendants:
            if not self.is_node_id_ancestor(node_id, descendant):
                return False
        return True

    def is_node_id_ancestor(self, node_id, descendant):
        """
        Checks that each ancestor's line of the descendant at some point only crossed node_id
        """
        if len(self.dependencies[descendant]) == 1 and node_id in self.dependencies[descendant]:
            return True
        for dependent in self.dependencies[descendant]:
            if len(self.dependencies[dependent]) == 0:
                return False
            if not self.is_node_id_ancestor(node_id, dependent):
                return False
        return True

    def get_last_occurrence(self, all_occurrences):
        """
        Get node id of node with the partially implemented spatial process that runs last
        """
        indices = [self.execution_order.index(occurrence["node_id"]) for occurrence in all_occurrences]
        return self.execution_order[max(indices)]

    def get_spatial_info(self):
        """
        Returns shapely geometry object in CRS 4326, original CRS, resolution and resampling method
        """
        return None, None, None, None
