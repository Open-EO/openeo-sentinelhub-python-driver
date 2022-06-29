from pg_to_evalscript.process_graph_utils import get_dependencies

from openeoerrors import PartiallySupportedProcessInvalid


class FilterBBox:
    def __init__(self, process_graph):
        self.process_id = "filter_bbox"
        self.process_graph = process_graph

    def get_all_occurrences_of_process_id(self, process_graph, process_id, level=0, all_occurrences=[]):
        for node_id, node in process_graph.items():
            if node["process_id"] == process_id:
                all_occurrences.append({"node_id": node_id, "level": level})
            for arg_name, arg_val in node["arguments"].items():
                if isinstance(arg_val, dict) and "process_graph" in arg_val:
                    self.get_all_occurrences_of_process_id(
                        arg_val["process_graph"], process_id, level=level + 1, all_occurrences=all_occurrences
                    )
        return all_occurrences

    def is_usage_valid(self):
        all_occurrences = self.get_all_occurrences_of_process_id(self.process_graph, self.process_id)

        for occurrence in all_occurrences:
            if occurrence["level"] > 0:
                raise PartiallySupportedProcessInvalid(
                    self.process_id,
                    "Process can only be used in the main processing chain. It cannot be used in processes inside other processes.",
                )
