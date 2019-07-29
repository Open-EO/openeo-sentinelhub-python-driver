from marshmallow import Schema, fields, ValidationError

class ProcessGraph(fields.Field):
    pass

class ProcessGraphsRequest:
	title = fields.Str(allow_none=True)
	description = fields.Str(allow_none=True)
	process_graph = fields.ProcessGraph(required=True)
