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

    # entity types correspond to DynamoDB tables:
    ET_PROCESS_GRAPHS = 'process_graphs'
    ET_JOBS = 'jobs'


    @classmethod
    def create(cls, entity_type, data):
        """
            Creates a new record and returns its record ID (UUID).
        """
        record_id = str(uuid.uuid4())
        cls.dynamodb.put_item(
            TableName=entity_type,
            Item={
                'id': {'S': record_id},
                'data': {'S': json.dumps(data)},
            },
        )
        return record_id


    @classmethod
    def items(cls, entity_type):
        paginator = cls.dynamodb.get_paginator('scan')
        for page in paginator.paginate(TableName=entity_type):
            for item in page["Items"]:
                yield item['id']['S'], json.loads(item['data']['S'])


    @classmethod
    def ensure_table_exists(cls, tableName):
        try:
            cls.dynamodb.create_table(
                AttributeDefinitions=[
                    {
                        'AttributeName': 'id',
                        'AttributeType': 'S',
                    },
                ],
                KeySchema=[
                    {
                        'AttributeName': 'id',
                        'KeyType': 'HASH',
                    },
                ],
                TableName=tableName,
                BillingMode='PAY_PER_REQUEST',  # we use on-demand pricing
            )
            log(INFO, "Successfully created DynamoDB table '{}'.".format(tableName))
        except cls.dynamodb.exceptions.ResourceInUseException:
            log(INFO, "DynamoDB table '{}' already exists, ignoring.".format(tableName))
            pass

Persistence.ensure_table_exists(Persistence.ET_PROCESS_GRAPHS)
Persistence.ensure_table_exists(Persistence.ET_JOBS)
