from marshmallow import Schema, fields, validates, ValidationError, validate
from openeo_pg_parser_python.validate_process_graph import validate_graph
import glob
import json
import os
import copy

def validate_graph_with_known_processes(graph):
	path_to_current_file = os.path.realpath(__file__)
	current_directory = os.path.dirname(path_to_current_file)
	path_to_files = os.path.join(current_directory, "process_definitions/*.json")

	files = glob.iglob(path_to_files)
	process_definitions = []
	for file in files:
		with open(file) as f:
			process_definitions.append(json.load(f))

	try:
		# validate_graph() changes process graph input, so we need to pass a cloned object:
		valid = validate_graph(copy.deepcopy(graph), process_definitions)
		if not valid:
			raise ValidationError("Invalid process graph")
	except Exception as e:
		raise ValidationError("Invalid process graph: " + str(e))


class PostProcessGraphsSchema(Schema):
	"""
	Request body
	POST /process_graphs
	"""
	title = fields.Str(allow_none=True)
	description = fields.Str(allow_none=True)
	process_graph = fields.Dict(required=True)

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

class PostJobsSchema(Schema):
	"""
	Request body
	POST /jobs
	"""
	process_graph = fields.Dict(required=True)
	description = fields.Str(allow_none=True)
	title = fields.Str(allow_none=True)
	plan = fields.Str(allow_none=True)
	budget = fields.Number(allow_none=True)

	@validates("process_graph")
	def validate_process_graph(self, graph):
		validate_graph_with_known_processes(graph)

class PatchJobsSchema(Schema):
	"""
	Request body
	POST /jobs
	"""
	process_graph = fields.Dict(allow_none=True)
	description = fields.Str(allow_none=True)
	title = fields.Str(allow_none=True)
	plan = fields.Str(allow_none=True)
	budget = fields.Number(allow_none=True)

	@validates("process_graph")
	def validate_process_graph(self, graph):
		validate_graph_with_known_processes(graph)

class PostResultSchema(Schema):
	"""
	Request body
	POST /result
	"""
	process_graph = fields.Dict(required=True)
	budget = fields.Number(allow_none=True)
	plan = fields.Str(allow_none=True)

	@validates("process_graph")
	def validate_process_graph(self, graph):
		validate_graph_with_known_processes(graph)

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
#curl -d "{\"process_graph\": {\"smth\": {\"process_id\": \"load_collection\", \"arguments\": {\"id\": {}, \"spatial_extent\": {}}}}}" -H "Content-Type: application/json" -X POST http://127.0.0.1:5000/process_graphs
# INCORRECT
#no process_id
#curl -d "{\"process_graph\": {\"test\": {\"arguments\": {\"id\": \"Sentinel-2\"}}}}" -H "Content-Type: application/json" -X POST http://127.0.0.1:5000/process_graphs
#process not supported
#curl -d "{\"process_graph\": {\"test\": {\"process_id\": \"dcgewk\", \"arguments\": {\"id\": \"Sentinel-2\"}}}}" -H "Content-Type: application/json" -X POST http://127.0.0.1:5000/process_graphs
#no process_graph
#curl -d "{\"title\": \"failure\"}" -H "Content-Type: application/json" -X POST http://127.0.0.1:5000/process_graphs
