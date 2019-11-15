import boto3
from boto3.dynamodb.conditions import Attr,Key
from botocore.exceptions import ClientError
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
SQS_LOCAL_URL = os.environ.get('SQS_LOCAL_URL', 'http://localhost:9324')
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

    TABLE_NAME = None

    @classmethod
    def items(cls):
        paginator = cls.dynamodb.get_paginator('scan')
        for page in paginator.paginate(TableName=cls.TABLE_NAME):
            for item in page["Items"]:
                for key,value in item.items():
                    data_type = list(value)[0]
                    item[key] = value[data_type]
                yield item

    @classmethod
    def delete(cls, record_id):
        cls.dynamodb.delete_item(TableName=cls.TABLE_NAME, Key={'id':{'S':record_id}})

    @classmethod
    def get_by_id(cls, record_id):
        item = cls.dynamodb.get_item(TableName=cls.TABLE_NAME, Key={'id':{'S':record_id}}).get("Item")

        if item is None:
            return None

        for key,value in item.items():
            data_type = list(value)[0]
            if key == "http_code":
                item[key] = int(value[data_type])
            else:
                item[key] = value[data_type]
        return item


    @classmethod
    def update_key(cls, record_id, key, new_value):
        data_type = 'S'
        if not isinstance(new_value, str):
            if isinstance(new_value, dict) or isinstance(new_value, list):
                new_value = json.dumps(new_value)
            elif isinstance(new_value, bool):
                data_type = 'BOOL'
            elif key == "http_code":
                data_type = 'N'
                new_value = str(new_value)
            else:
                new_value = str(new_value)

        updated_item = cls.dynamodb.update_item(TableName=cls.TABLE_NAME, Key={'id':{'S':record_id}}, UpdateExpression="SET {} = :new_content".format(key), ExpressionAttributeValues={':new_content': {data_type: new_value}})
        return updated_item

    @classmethod
    def ensure_table_exists(cls):
        log(INFO, "Ensuring DynamoDB table exists: '{}'.".format(cls.TABLE_NAME))
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
                TableName=cls.TABLE_NAME,
                BillingMode='PAY_PER_REQUEST',  # we use on-demand pricing
            )
            log(INFO, "Successfully created DynamoDB table '{}'.".format(cls.TABLE_NAME))
        except cls.dynamodb.exceptions.ResourceInUseException:
            log(INFO, "DynamoDB table '{}' already exists, ignoring.".format(cls.TABLE_NAME))

    @classmethod
    def delete_table(cls):
        try:
            #TableName=
            cls.dynamodb.delete_table(TableName=cls.TABLE_NAME)
            log(INFO, "Table {} Successfully deleted.".format(cls.TABLE_NAME))
        except:
            log(INFO, "Table {} does not exists.".format(cls.TABLE_NAME))

    @classmethod
    def clear_table(cls):
        for item in cls.items():
            cls.delete(item["id"])


class JobsPersistence(Persistence):
    TABLE_NAME = 'shopeneo_jobs'
    SQS_QUEUE_NAME = 'shopeneo-jobs-queue'
    sqs = boto3.client('sqs',
        region_name="eu-central-1",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    ) if DYNAMODB_PRODUCTION else boto3.client('sqs',
        endpoint_url=SQS_LOCAL_URL,
        region_name="eu-central-1",
        aws_access_key_id='x',
        aws_secret_access_key='x'
    )

    @classmethod
    def create(cls, data):
        """
            Creates a new record and returns its record ID (UUID).
        """
        record_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        item = {
            'id': {'S': record_id},
            'process_graph': {'S': json.dumps(data.get("process_graph"))},
            'current_status': {'S': str(data.get("current_status", "queued"))},
            'submitted': {'S': timestamp},
            'last_updated': {'S': timestamp},
            'should_be_cancelled': {'BOOL': data.get("should_be_cancelled", False)},
            'error_msg': {'S': str(data.get("error_msg"))},
            'error_code': {'S': str(data.get("error_code"))},
            'http_code': {'N':data.get("http_code", "200")},
            'results': {'S': json.dumps(data.get("results"))},
        }
        if data.get("title"):
            item["title"] = {'S': str(data.get("title"))}
        if data.get("description"):
            item["description"] = {'S': str(data.get("description"))}
        if data.get("variables"):
            item["variables"] = {'S': json.dumps(data.get("variables"))}
        if data.get("plan"):
            item['plan'] = {'S': str(data.get("plan"))}
        if data.get("budget"):
            item['budget'] = {'S': str(data.get("budget"))}

        cls.dynamodb.put_item(
            TableName=cls.TABLE_NAME,
            Item=item,
        )

        # notify workers that a new job is available:
        queue_url = cls.sqs.get_queue_url(QueueName=cls.SQS_QUEUE_NAME)['QueueUrl']
        response = cls.sqs.send_message(QueueUrl=queue_url, MessageBody=record_id)

        return record_id

    @classmethod
    def ensure_queue_exists(cls):
        try:
            cls.sqs.create_queue(QueueName=cls.SQS_QUEUE_NAME, Attributes={
                'DelaySeconds': '0',
                'MessageRetentionPeriod': '60',
                'ReceiveMessageWaitTimeSeconds': '20',
            })
            log(INFO, "SQS queue created.")
        except ClientError:
            log(INFO, "SQS queue already exists.")


class ProcessGraphsPersistence(Persistence):
    TABLE_NAME = 'shopeneo_process_graphs'

    @classmethod
    def create(cls, data):
        """
            Creates a new record and returns its record ID (UUID).
        """
        record_id = str(uuid.uuid4())
        item = {
            'id': {'S': record_id},
            'process_graph': {'S': json.dumps(data.get("process_graph"))},
        }
        if data.get("title"):
            item["title"] = {'S': str(data.get("title"))}
        if data.get("description"):
            item["description"] = {'S': str(data.get("description"))}

        cls.dynamodb.put_item(
            TableName=cls.TABLE_NAME,
            Item=item,
        )
        return record_id


class ServicesPersistence(Persistence):
    TABLE_NAME = 'shopeneo_services'

    @classmethod
    def create(cls, data):
        """
            Creates a new record and returns its record ID (UUID).
        """
        record_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        item = {
            'id': {'S': record_id},
            'service_type': {'S': str(data.get("type"))},
            'process_graph': {'S': json.dumps(data.get("process_graph"))},
            'enabled': {'BOOL': data.get("enabled", True)},
            'parameters': {'S': str(data.get("parameters"))},
            'submitted': {'S': timestamp},
        }
        for optional_field in ["title", "description", "plan", "budget"]:
            if data.get(optional_field) is not None:
                item[optional_field] = {'S': str(data.get(optional_field))}

        cls.dynamodb.put_item(
            TableName=cls.TABLE_NAME,
            Item=item,
        )
        return record_id


if __name__ == "__main__":

    # To create tables, run:
    #   $ pipenv shell
    #   <shell> $ DYNAMODB_PRODUCTION=yes ./dynamodb.py
    #
    # Currently it is not posible to create tables from the Lambda because the
    # boto3 version included is too old, and we can't upload newer one (creating
    # tables doesn't work if we do that)

    log(INFO, "Initializing DynamoDB (url: {}, production: {})...".format(DYNAMODB_LOCAL_URL, DYNAMODB_PRODUCTION))
    JobsPersistence.ensure_table_exists()
    JobsPersistence.ensure_queue_exists()
    ProcessGraphsPersistence.ensure_table_exists()
    ServicesPersistence.ensure_table_exists()
    log(INFO, "DynamoDB initialized.")
