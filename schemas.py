from marshmallow import Schema, fields, validates, ValidationError, validate
from openeo_pg_parser_python.validate_process_graph import validate_graph

def validate_graph_with_known_processes(graph):
	valid = validate_graph(graph, [
		{"id": "load_collection", "parameters": {"id": {}, "spatial_extent": {}}}
	])
	if not valid:
		raise ValidationError("Invalid process graph")

class PostProcessGraphsSchema(Schema):
	"""
	Request body
	POST /process_graphs and PATCH /process_graphs
	"""
	title = fields.Str(allow_none=True)
	description = fields.Str(allow_none=True)
	process_graph = fields.Dict(required=True)

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
#curl -d "{\"process_graph\": {\"test\": {\"process_id\": \"test\", \"arguments\": {\"id\": \"Sentinel-2\"}}}}" -H "Content-Type: application/json" -X POST http://127.0.0.1:5000/process_graphs
# INCORRECT
#no process_id
#curl -d "{\"process_graph\": {\"test\": {\"arguments\": {\"id\": \"Sentinel-2\"}}}}" -H "Content-Type: application/json" -X POST http://127.0.0.1:5000/process_graphs
#process not supported
#curl -d "{\"process_graph\": {\"test\": {\"process_id\": \"dcgewk\", \"arguments\": {\"id\": \"Sentinel-2\"}}}}" -H "Content-Type: application/json" -X POST http://127.0.0.1:5000/process_graphs
#no process_graph
#curl -d "{\"title\": \"failure\"}" -H "Content-Type: application/json" -X POST http://127.0.0.1:5000/process_graphs
