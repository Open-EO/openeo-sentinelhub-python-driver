import boto3
from boto3.dynamodb.conditions import Attr,Key
import json
import logging
from logging import log, INFO
import os
import uuid
import datetime


logging.basicConfig(level=logging.INFO)


FAKE_AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
FAKE_AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


# we use local DynamoDB by default, to avoid using AWS for testing by mistake
DYNAMODB_PRODUCTION = os.environ.get('DYNAMODB_PRODUCTION', '').lower() in ["true", "1", "yes"]
DYNAMODB_LOCAL_URL = os.environ.get('DYNAMODB_LOCAL_URL', 'http://localhost:8000')
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', FAKE_AWS_ACCESS_KEY_ID)
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', FAKE_AWS_SECRET_ACCESS_KEY)

class Persistence(object):
    dynamodb = boto3.client('dynamodb',
        region_name="eu-central-1",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    ) if DYNAMODB_PRODUCTION else boto3.client('dynamodb',
        endpoint_url=DYNAMODB_LOCAL_URL,
        region_name="eu-central-1",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

    # entity types correspond to DynamoDB tables:
    ET_PROCESS_GRAPHS = 'shopeneo_process_graphs'
    ET_JOBS = 'shopeneo_jobs'

    @classmethod
    def create(cls, entity_type, data):
        """
            Creates a new record and returns its record ID (UUID).
        """
        record_id = str(uuid.uuid4())
        
        if entity_type == cls.ET_JOBS:
            item = {
                'id': {'S': record_id},
                'process_graph': {'S': json.dumps(data.get("process_graph"))},
                'plan': {'S': str(data.get("plan"))},
                'budget': {'S': str(data.get("budget"))},
                'current_status': {'S': str(data.get("current_status"))},
                'submitted': {'S': str(data.get("submitted"))},
                'last_updated': {'S': str(data.get("last_updated"))},
                'should_be_cancelled': {'BOOL': data.get("should_be_cancelled")},
                'error_msg': {'S': str(data.get("error_msg"))},
                'results': {'S': json.dumps(data.get("results"))},
            }
        elif entity_type == cls.ET_PROCESS_GRAPHS:
            item = {
                'id': {'S': record_id},
                'process_graph': {'S': json.dumps(data.get("process_graph"))},
            }

        if data.get("title"):
            item["title"] = {'S': str(data.get("title"))}
        if data.get("description"):
            item["description"] = {'S': str(data.get("description"))}
        cls.dynamodb.put_item(
            TableName=entity_type,
            Item=item,
        )
        return record_id

    @classmethod
    def items(cls, entity_type):
        paginator = cls.dynamodb.get_paginator('scan')
        for page in paginator.paginate(TableName=entity_type):
            for item in page["Items"]:
                for key,value in item.items():
                    data_type = list(value)[0]
                    item[key] = value[data_type]
                yield item

    @classmethod
    def delete(cls, entity_type, record_id):
        cls.dynamodb.delete_item(TableName=entity_type, Key={'id':{'S':record_id}})

    @classmethod
    def get_by_id(cls, entity_type, record_id):
        item = cls.dynamodb.get_item(TableName=entity_type, Key={'id':{'S':record_id}}).get("Item")

        if item is None:
            return None

        for key,value in item.items():
            data_type = list(value)[0]
            item[key] = value[data_type]

        return item


    @classmethod
    def update_key(cls, entity_type, record_id, key, new_value):
        data_type = 'S'
        if not isinstance(new_value, str):
            if isinstance(new_value, dict) or isinstance(new_value, list):
                new_value = json.dumps(new_value)
            elif key == "should_be_cancelled":
                data_type = 'BOOL'
            else:
                new_value = str(new_value)

        updated_item = cls.dynamodb.update_item(TableName=entity_type, Key={'id':{'S':record_id}}, UpdateExpression="SET {} = :new_content".format(key), ExpressionAttributeValues={':new_content': {data_type: new_value}})
        return updated_item

    @classmethod
    def ensure_table_exists(cls, table_name):
        log(INFO, "Ensuring DynamoDB table exists: '{}'.".format(table_name))
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
                TableName=table_name,
                BillingMode='PAY_PER_REQUEST',  # we use on-demand pricing
            )
            log(INFO, "Successfully created DynamoDB table '{}'.".format(table_name))
        except cls.dynamodb.exceptions.ResourceInUseException:
            log(INFO, "DynamoDB table '{}' already exists, ignoring.".format(table_name))

    @classmethod
    def delete_table(cls, table_name):
        try:
            #TableName=
            cls.dynamodb.delete_table(TableName=table_name)
            log(INFO, "Table {} Successfully deleted.".format(table_name))
        except:
            log(INFO, "Table {} does not exists.".format(table_name))


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
    Persistence.ensure_table_exists(Persistence.ET_JOBS)
    log(INFO, "DynamoDB initialized.")
