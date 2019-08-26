import boto3
from boto3.dynamodb.conditions import Attr,Key
import json
import logging
from logging import log, INFO
import os
import uuid


logging.basicConfig(level=logging.INFO)


FAKE_AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
FAKE_AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


# we use local DynamoDB by default, to avoid using AWS for testing by mistake
DYNAMODB_PRODUCTION = os.environ.get('DYNAMODB_PRODUCTION', '').lower() in ["true", "1", "yes"]
DYNAMODB_LOCAL_URL = os.environ.get('DYNAMODB_LOCAL_URL', 'http://localhost:8000')
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', FAKE_AWS_ACCESS_KEY_ID)
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', FAKE_AWS_SECRET_ACCESS_KEY)

class Persistence(object):
    dynamodb = boto3.client('dynamodb') if DYNAMODB_PRODUCTION else \
        boto3.client('dynamodb', endpoint_url=DYNAMODB_LOCAL_URL,region_name="eu-central-1",aws_access_key_id=AWS_ACCESS_KEY_ID,aws_secret_access_key=AWS_SECRET_ACCESS_KEY)


    # entity types correspond to DynamoDB tables:
    ET_PROCESS_GRAPHS = 'shopeneo_process_graphs'
    ET_JOBS = 'shopeneo_jobs'


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
    def delete(cls, entity_type, record_id):
        cls.dynamodb.delete_item(TableName=entity_type, Key={'id':{'S':record_id}})

    @classmethod
    def get_by_id(cls, entity_type, record_id):
        graph = cls.dynamodb.get_item(TableName=entity_type, Key={'id':{'S':record_id}})
        return graph

    @classmethod
    def replace(cls, entity_type, record_id, data):
        new_data = cls.dynamodb.update_item(TableName=entity_type, Key={'id':{'S':record_id}}, UpdateExpression="SET data = :new_data", ExpressionAttributeValues={':new_data':data})
        return new_data

    @classmethod
    def ensure_table_exists(cls, table_name, stream_enabled=False):
        log(INFO, "Ensuring DynamoDB table exists: '{}'.".format(table_name))
        try:
            if stream_enabled:
                stream_specification={'StreamEnabled': True, 'StreamViewType': 'KEYS_ONLY'}
            else:
                stream_specification={'StreamEnabled': False}

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
                TableName=table_name,
                BillingMode='PAY_PER_REQUEST',  # we use on-demand pricing
                StreamSpecification=stream_specification,
            )
            log(INFO, "Successfully created DynamoDB table '{}'.".format(table_name))
        except cls.dynamodb.exceptions.ResourceInUseException:
            log(INFO, "DynamoDB table '{}' already exists, ignoring.".format(table_name))
            pass


if __name__ == "__main__":

    # To create tables, run:
    #   $ pipenv shell
    #   <shell> $ DYNAMODB_PRODUCTION=yes ./dynamodb.py
    #
    # Currently it is not posible to create tables from the Lambda because the
    # boto3 version included is too old, and we can't upload newer one (creating
    # tables doesn't work if we do that)

    log(INFO, "Initializing DynamoDB (url: {}, production: {})...".format(DYNAMODB_LOCAL_URL, DYNAMODB_PRODUCTION))
    Persistence.ensure_table_exists(Persistence.ET_PROCESS_GRAPHS)
    Persistence.ensure_table_exists(Persistence.ET_JOBS, True)
    log(INFO, "DynamoDB initialized.")
