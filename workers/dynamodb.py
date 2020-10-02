import json
import logging
from logging import log, INFO
import os
import uuid
import datetime

import boto3
from boto3.dynamodb.conditions import Attr, Key
import botocore.exceptions


logging.basicConfig(level=logging.INFO)


FAKE_AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
FAKE_AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


# we use local DynamoDB by default, to avoid using AWS for testing by mistake
DYNAMODB_PRODUCTION = os.environ.get("DYNAMODB_PRODUCTION", "").lower() in ["true", "1", "yes"]
DYNAMODB_LOCAL_URL = os.environ.get("DYNAMODB_LOCAL_URL", "http://localhost:8000")
SQS_LOCAL_URL = os.environ.get("SQS_LOCAL_URL", "http://localhost:9324")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", FAKE_AWS_ACCESS_KEY_ID)
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", FAKE_AWS_SECRET_ACCESS_KEY)


class JobsPersistence(object):
    dynamodb = (
        boto3.client("dynamodb")
        if DYNAMODB_PRODUCTION
        else boto3.client(
            "dynamodb",
            endpoint_url=DYNAMODB_LOCAL_URL,
            region_name="eu-central-1",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )
    )
    sqs = (
        boto3.client(
            "sqs",
            region_name="eu-central-1",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )
        if DYNAMODB_PRODUCTION
        else boto3.client(
            "sqs",
            endpoint_url=SQS_LOCAL_URL,
            region_name="eu-central-1",
            aws_access_key_id="x",
            aws_secret_access_key="x",
        )
    )

    # entity types correspond to DynamoDB tables:
    ET_JOBS = "shopeneo_jobs"
    SQS_QUEUE_NAME = "shopeneo-jobs-queue"

    @classmethod
    def wait_for_wakeup(cls, timeout=20):
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sqs.html
        queue_url = cls.sqs.get_queue_url(QueueName=cls.SQS_QUEUE_NAME)["QueueUrl"]

        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sqs.html#SQS.Queue.receive_messages
        # When we receive the message, it is kept hidden from others for 61 seconds, which is more than
        # MessageRetentionPeriod (60s) - which essentially means that noone else can retrieve it.
        messages = cls.sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,  # max. 10
            WaitTimeSeconds=20,
        )
        if not messages.get("Messages"):
            return []
        delete_batch_entries = [
            {"Id": str(i + 1), "ReceiptHandle": m["ReceiptHandle"]} for i, m in enumerate(messages["Messages"])
        ]
        cls.sqs.delete_message_batch(QueueUrl=queue_url, Entries=delete_batch_entries)
        job_ids = [m["Body"] for m in messages["Messages"]]
        return job_ids

    @classmethod
    def query_new_queued(cls):
        paginator = cls.dynamodb.get_paginator("scan")
        paginator = paginator.paginate(
            TableName=cls.ET_JOBS,
            FilterExpression="current_status = :current_status AND should_be_cancelled = :should_be_cancelled",
            ExpressionAttributeValues={":current_status": {"S": "queued"}, ":should_be_cancelled": {"BOOL": False}},
        )
        return paginator

    @classmethod
    def query_cancelled_queued(cls):
        paginator = cls.dynamodb.get_paginator("scan")
        paginator = paginator.paginate(
            TableName=cls.ET_JOBS,
            FilterExpression="current_status = :current_status AND should_be_cancelled = :should_be_cancelled",
            ExpressionAttributeValues={":current_status": {"S": "queued"}, ":should_be_cancelled": {"BOOL": True}},
        )
        return paginator

    @classmethod
    def query_cancelled_running(cls):
        paginator = cls.dynamodb.get_paginator("scan")
        paginator = paginator.paginate(
            TableName=cls.ET_JOBS,
            FilterExpression="current_status = :current_status AND should_be_cancelled = :should_be_cancelled",
            ExpressionAttributeValues={":current_status": {"S": "running"}, ":should_be_cancelled": {"BOOL": True}},
        )
        return paginator

    @classmethod
    def update_queued_to_running(cls, record_id):
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        updated_item = cls.dynamodb.update_item(
            TableName=cls.ET_JOBS,
            Key={"id": {"S": record_id}},
            UpdateExpression="SET current_status = :new_status, last_updated = :timestamp",
            ExpressionAttributeValues={
                ":new_status": {"S": "running"},
                ":timestamp": {"S": timestamp},
                ":old_status": {"S": "queued"},
            },
            ReturnValues="UPDATED_NEW",
            ConditionExpression="current_status = :old_status",
        )
        return updated_item

    @classmethod
    def update_running_to_finished(cls, record_id, results, error_msg=None, error_code=None, http_code=None):
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        # depending on whether error_msg is set, update either results or error_msg field:
        if error_msg:
            update_expression = "SET current_status = :new_status, error_msg = :error_msg, error_code = :error_code, http_code = :http_code, last_updated = :timestamp, auth_token = :auth_token"
            values = {
                ":old_status": {"S": "running"},
                ":new_status": {"S": "error"},
                ":timestamp": {"S": timestamp},
                ":error_msg": {"S": error_msg},
                ":error_code": {"S": str(error_code)},
                ":http_code": {"S": str(http_code)},
                ":auth_token": {"S": "/"},  # DynamoDB doesn't allow empty strings
            }
        else:
            update_expression = "SET current_status = :new_status, results = :results, last_updated = :timestamp, auth_token = :auth_token"
            values = {
                ":old_status": {"S": "running"},
                ":new_status": {"S": "finished"},
                ":timestamp": {"S": timestamp},
                ":results": {"S": json.dumps(results)},
                ":auth_token": {"S": "/"},
            }
        try:
            updated_item = cls.dynamodb.update_item(
                TableName=cls.ET_JOBS,
                Key={"id": {"S": record_id}},
                ConditionExpression="current_status = :old_status",
                UpdateExpression=update_expression,
                ExpressionAttributeValues=values,
                ReturnValues="UPDATED_NEW",
            )
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                log(
                    INFO,
                    "Job {} could not be updated to finished/error, it was probably already removed due to timeout - ignoring error.".format(
                        record_id
                    ),
                )
            else:
                raise

    @classmethod
    def update_cancelled_queued_to_created(cls, record_id):
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        updated_item = cls.dynamodb.update_item(
            TableName=cls.ET_JOBS,
            Key={"id": {"S": record_id}},
            UpdateExpression="SET current_status = :new_status, last_updated = :timestamp, should_be_cancelled = :should_be_cancelled, auth_token = :auth_token",
            ExpressionAttributeValues={
                ":new_status": {"S": "created"},
                ":timestamp": {"S": timestamp},
                ":should_be_cancelled": {"BOOL": False},
                ":old_status": {"S": "queued"},
                ":auth_token": {"S": "/"},
            },
            ReturnValues="UPDATED_NEW",
            ConditionExpression="current_status = :old_status",
        )
        return updated_item

    @classmethod
    def update_cancelled_running_to_canceled(cls, record_id):
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        updated_item = cls.dynamodb.update_item(
            TableName=cls.ET_JOBS,
            Key={"id": {"S": record_id}},
            UpdateExpression="SET current_status = :new_status, last_updated = :timestamp, should_be_cancelled = :should_be_cancelled, auth_token = :auth_token",
            ExpressionAttributeValues={
                ":new_status": {"S": "canceled"},
                ":timestamp": {"S": timestamp},
                ":should_be_cancelled": {"BOOL": False},
                ":old_status": {"S": "running"},
                ":auth_token": {"S": "/"},
            },
            ReturnValues="UPDATED_NEW",
            ConditionExpression="current_status = :old_status",
        )
        return updated_item
