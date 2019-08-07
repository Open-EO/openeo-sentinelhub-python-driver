from marshmallow import Schema, fields, validates, ValidationError
from openeo_pg_parser_python.validate_process_graph import validate_graph

class ProcessGraphsRequest(Schema):
	title = fields.Str(allow_none=True)
	description = fields.Str(allow_none=True)
	process_graph = fields.Dict(required=True)

	@validates("process_graph")
	def validate_process_graph(self,graph):
		valid = validate_graph(graph,[{"id":"test","parameters":{"id": {}}}])
		if not valid:
			raise ValidationError("Invalid process graph")

# CORRECT
#curl -d "{\"process_graph\": {\"test\": {\"process_id\": \"test\", \"arguments\": {\"id\": \"Sentinel-2\"}}}}" -H "Content-Type: application/json" -X POST http://127.0.0.1:5000/test
# INCORRECT
#no process_id
#curl -d "{\"process_graph\": {\"test\": {\"arguments\": {\"id\": \"Sentinel-2\"}}}}" -H "Content-Type: application/json" -X POST http://127.0.0.1:5000/test
#process not supported
#curl -d "{\"process_graph\": {\"test\": {\"process_id\": \"dcgewk\", \"arguments\": {\"id\": \"Sentinel-2\"}}}}" -H "Content-Type: application/json" -X POST http://127.0.0.1:5000/test
#no process_graph
#curl -d "{\"title\": \"failure\"}" -H "Content-Type: application/json" -X POST http://127.0.0.1:5000/test

