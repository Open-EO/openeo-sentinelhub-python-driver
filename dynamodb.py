import uuid


class Persistence(object):
    @classmethod
    def create(cls, entity_type, data):
        """
            Creates a new record and returns its id (uuid).
        """
        record_id = str(uuid.uuid4())
        return record_id

    @classmethod
    def items(cls, entity_type):
        for _ in range(10):
            yield str(uuid.uuid4()), {"title": "Storage not implemented yet."}
