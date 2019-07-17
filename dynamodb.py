import boto3
import json
from logging import log, INFO
import os
import uuid


# we use local DynamoDB by default, to avoid using AWS for testing by mistake
DYNAMODB_PRODUCTION = os.environ.get('DYNAMODB_PRODUCTION', '').lower() in ["true", "1", "yes"]


class Persistence(object):
    dynamodb = boto3.client('dynamodb') if DYNAMODB_PRODUCTION else \
        boto3.client('dynamodb', endpoint_url='http://localhost:8000')

    # entity types:
    ET_PROCESS_GRAPHS = 'process_graphs'
    ET_JOBS = 'jobs'


    @staticmethod
    def _entity_id(entity_type, record_id):
        """ Creates entity ID from the entity type and record ID (which is UUID). """
        return "{}.{}".format(entity_type, record_id)


    @classmethod
    def create(cls, entity_type, data):
        """
            Creates a new record and returns its record ID (UUID).
        """
        record_id = str(uuid.uuid4())
        entity_id = Persistence._entity_id(entity_type, record_id)
        print(entity_id)
        cls.dynamodb.put_item(
            TableName='entities',
            Item={
                'entityId': {'S': entity_id},
                'data': {'S': json.dumps(data)},
            },
        )
        return record_id


    @classmethod
    def items(cls, entity_type):
        for _ in range(10):
            yield str(uuid.uuid4()), {"title": "Not implemented yet."}


    @classmethod
    def ensure_table_exists(cls):
        try:
            cls.dynamodb.create_table(
                AttributeDefinitions=[
                    {
                        'AttributeName': 'entityId',
                        'AttributeType': 'S',
                    },
                ],
                KeySchema=[
                    {
                        'AttributeName': 'entityId',
                        'KeyType': 'HASH',
                    },
                ],
                TableName='entities',
                BillingMode='PAY_PER_REQUEST',  # we use on-demand pricing
            )
            log(INFO, "Successfully created DynamoDB table 'entities'.")
        except cls.dynamodb.exceptions.ResourceInUseException:
            log(INFO, "DynamoDB table 'entities' already exists.")
            pass

Persistence.ensure_table_exists()