import copy
import glob
import json
from logging import log, INFO
import os
import traceback

from marshmallow import Schema, fields, validates, ValidationError, validate
from openeo_pg_parser.validate import validate_process_graph


def validate_graph_with_known_processes(graph):
    path_to_current_file = os.path.realpath(__file__)
    current_directory = os.path.dirname(path_to_current_file)
    path_to_collection_information = os.path.join(current_directory, "collection_information")
    path_to_process_definitions = os.path.join(current_directory, "process_definitions")

    try:
        # validate_graph() changes process graph input, so we need to pass a cloned object:
        process = {"process_graph": copy.deepcopy(graph)}
        valid = validate_process_graph(process, path_to_collection_information, path_to_process_definitions)
        if not valid:
            raise ValidationError("Invalid process graph")
    except Exception as e:
        log(INFO, traceback.format_exc())
        raise ValidationError("Invalid process graph: " + str(e))


class PutProcessGraphSchema(Schema):
    """
    Request body
    PUT /process_graphs/process_graph_id
    """

    process_graph = fields.Dict(required=True)
    process_id = fields.Str(allow_none=True, data_key="id", validate=validate.Regexp(r"^\w+$"))
    summary = fields.Str(allow_none=True)
    description = fields.Str(allow_none=True)
    categories = fields.List(fields.Str(allow_none=True), allow_none=True)
    parameters = fields.List(fields.Dict(allow_none=True), allow_none=True)
    returns = fields.Dict(allow_none=True)
    deprecated = fields.Bool(allow_none=True)
    experimental = fields.Bool(allow_none=True)
    exceptions = fields.Dict(allow_none=True)
    examples = fields.List(fields.Dict(allow_none=True), allow_none=True)
    links = fields.List(fields.Dict(allow_none=True), allow_none=True)

    @validates("process_graph")
    def validate_process_graph(self, graph):
        validate_graph_with_known_processes(graph)


class PatchProcessGraphsSchema(Schema):
    """
    Request body
    PATCH /process_graphs
    """

    title = fields.Str(allow_none=True)
    description = fields.Str(allow_none=True)
    process_graph = fields.Dict(allow_none=True)

    @validates("process_graph")
    def validate_process_graph(self, graph):
        validate_graph_with_known_processes(graph)


class ProcessSchema(Schema):
    """
    Request body
    POST /jobs
    'process' field
    """

    process_graph = fields.Dict(required=True)
    process_id = fields.Str(allow_none=True, data_key="id")
    summary = fields.Str(allow_none=True)
    description = fields.Str(allow_none=True)
    categories = fields.List(fields.Str(allow_none=True), allow_none=True)
    parameters = fields.List(fields.Dict(allow_none=True), allow_none=True)
    returns = fields.Dict(allow_none=True)
    deprecated = fields.Bool(allow_none=True)
    experimental = fields.Bool(allow_none=True)
    exceptions = fields.Dict(allow_none=True)
    examples = fields.List(fields.Dict(allow_none=True), allow_none=True)
    links = fields.List(fields.Dict(allow_none=True), allow_none=True)

    @validates("process_graph")
    def validate_process_graph(self, graph):
        validate_graph_with_known_processes(graph)


class PostJobsSchema(Schema):
    """
    Request body
    POST /jobs
    """

    process = fields.Nested(ProcessSchema, required=True)
    description = fields.Str(allow_none=True)
    title = fields.Str(allow_none=True)
    plan = fields.Str(allow_none=True)
    budget = fields.Number(allow_none=True)


class PatchJobsSchema(Schema):
    """
    Request body
    PATCH /jobs
    """

    process = fields.Nested(ProcessSchema, allow_none=True)
    description = fields.Str(allow_none=True)
    title = fields.Str(allow_none=True)
    plan = fields.Str(allow_none=True)
    budget = fields.Number(allow_none=True)


class PostServicesSchema(Schema):
    """
    Request body
    POST /services
    """

    title = fields.Str(allow_none=True)
    description = fields.Str(allow_none=True)
    process = fields.Nested(ProcessSchema, required=True)
    service_type = fields.Str(required=True, data_key="type")
    enabled = fields.Bool(allow_none=True)
    configuration = fields.Dict(allow_none=True)
    plan = fields.Str(allow_none=True)
    budget = fields.Number(allow_none=True)

    @validates("service_type")
    def validate_service_type(self, service_type):
        if service_type.lower() not in ["xyz"]:
            raise ValidationError("Only XYZ service type is supported")


class PatchServicesSchema(Schema):
    """
    Request body
    PATCH /services
    """

    title = fields.Str(allow_none=True)
    description = fields.Str(allow_none=True)
    process = fields.Nested(ProcessSchema, allow_none=True)
    enabled = fields.Bool(allow_none=True)
    parameters = fields.Dict(allow_none=True)
    plan = fields.Str(allow_none=True)
    budget = fields.Number(allow_none=True)


class PostResultSchema(Schema):
    """
    Request body
    POST /result
    """

    process = fields.Nested(ProcessSchema, required=True)
    budget = fields.Number(allow_none=True)
    plan = fields.Str(allow_none=True)


class PGValidationSchema(Schema):
    """
    Request body
    POST /validation
    """

    process_graph = fields.Dict(required=True)

    @validates("process_graph")
    def validate_process_graph(self, graph):
        validate_graph_with_known_processes(graph)


# CORRECT
# curl -d "{\"process_graph\": {\"smth\": {\"process_id\": \"load_collection\", \"arguments\": {\"id\": {}, \"spatial_extent\": {}}}}}" -H "Content-Type: application/json" -X POST http://127.0.0.1:5000/process_graphs
# INCORRECT
# no process_id
# curl -d "{\"process_graph\": {\"test\": {\"arguments\": {\"id\": \"Sentinel-2\"}}}}" -H "Content-Type: application/json" -X POST http://127.0.0.1:5000/process_graphs
# process not supported
# curl -d "{\"process_graph\": {\"test\": {\"process_id\": \"dcgewk\", \"arguments\": {\"id\": \"Sentinel-2\"}}}}" -H "Content-Type: application/json" -X POST http://127.0.0.1:5000/process_graphs
# no process_graph
# curl -d "{\"title\": \"failure\"}" -H "Content-Type: application/json" -X POST http://127.0.0.1:5000/process_graphs
