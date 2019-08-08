import boto3
from boto3.dynamodb.conditions import Attr,Key
import json
from logging import log, INFO
import os
import uuid


# we use local DynamoDB by default, to avoid using AWS for testing by mistake
print("Production: ",os.environ.get('DYNAMODB_PRODUCTION', ''))
DYNAMODB_PRODUCTION = os.environ.get('DYNAMODB_PRODUCTION', '').lower() in ["true", "1", "yes"]
endpoint_url = 'http://dynamodb:8000' if os.environ.get('DYNAMODB_PRODUCTION', '') == "testing" else 'http://localhost:8000'

class Persistence(object):
    print("Production?",DYNAMODB_PRODUCTION)
    dynamodb = boto3.client('dynamodb') if DYNAMODB_PRODUCTION else \
        boto3.client('dynamodb', endpoint_url=endpoint_url,region_name="eu-central-1",aws_access_key_id="AKIAIOSFODNN7EXAMPLE",aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")


    # entity types correspond to DynamoDB tables:
    ET_PROCESS_GRAPHS = 'process_graphs'
    ET_JOBS = 'jobs'


    @classmethod
    def create(cls, entity_type, data):
        """
            Creates a new record and returns its record ID (UUID).
        """
        print("Data at create:",data)
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
    def get_by_id(cls,entity_type,id):
        graph = cls.dynamodb.get_item(TableName=entity_type, Key={'id':{'S':record_id}})
        return graph

    @classmethod
    def replace(cls,entity_type,id,data):
        new_data = cls.dynamodb.update_item(TableName=entity_type, Key={'id':{'S':record_id}}, UpdateExpression="SET data = :new_data", ExpressionAttributeValues={':new_data':data})
        return new_data

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

print("Ensuring")
Persistence.ensure_table_exists(Persistence.ET_PROCESS_GRAPHS)
Persistence.ensure_table_exists(Persistence.ET_JOBS)
print("Ensuring finished")

