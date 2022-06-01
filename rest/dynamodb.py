import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError
import json
import logging
from logging import log, INFO
import os
import uuid
import datetime
from enum import Enum


logging.basicConfig(level=logging.INFO)


FAKE_AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
FAKE_AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


class DeploymentTypes(Enum):
    PRODUCTION = "production"
    TESTING = "testing"

    @staticmethod
    def from_string(deployment_type_str):
        deployment_type_str_to_enum = {
            "production": DeploymentTypes.PRODUCTION,
            "testing": DeploymentTypes.TESTING,
        }
        return deployment_type_str_to_enum.get(deployment_type_str)


DEPLOYMENT_TYPE = DeploymentTypes.from_string(os.environ.get("DEPLOYMENT_TYPE", "").lower())

if DEPLOYMENT_TYPE == DeploymentTypes.PRODUCTION:
    TABLE_NAME_PREFIX = ""
elif DEPLOYMENT_TYPE == DeploymentTypes.TESTING:
    TABLE_NAME_PREFIX = "testing"
else:
    TABLE_NAME_PREFIX = "local"

# we use local DynamoDB by default, to avoid using AWS for testing by mistake
DYNAMODB_LOCAL_URL = os.environ.get("DYNAMODB_LOCAL_URL", "http://localhost:8000")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", FAKE_AWS_ACCESS_KEY_ID)
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", FAKE_AWS_SECRET_ACCESS_KEY)


class Persistence(object):
    dynamodb = (
        boto3.client(
            "dynamodb",
            region_name="eu-central-1",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )
        if DEPLOYMENT_TYPE in [DeploymentTypes.PRODUCTION, DeploymentTypes.TESTING]
        else boto3.client(
            "dynamodb",
            endpoint_url=DYNAMODB_LOCAL_URL,
            region_name="eu-central-1",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )
    )

    TABLE_NAME = None

    @classmethod
    def items(cls):
        paginator = cls.dynamodb.get_paginator("scan")
        for page in paginator.paginate(TableName=cls.TABLE_NAME):
            for item in page["Items"]:
                yield cls.prepare_loaded_item(item)

    @classmethod
    def query_by_user_id(cls, user_id):
        paginator = cls.dynamodb.get_paginator("query")
        for page in paginator.paginate(
            TableName=cls.TABLE_NAME,
            IndexName="user_id",
            KeyConditionExpression="#itemskey = :itemsvalue",
            ExpressionAttributeNames={"#itemskey": "user_id"},
            ExpressionAttributeValues={":itemsvalue": {"S": user_id}},
        ):
            for item in page["Items"]:
                yield cls.prepare_loaded_item(item)

    @classmethod
    def delete(cls, record_id):
        cls.dynamodb.delete_item(TableName=cls.TABLE_NAME, Key={"id": {"S": record_id}})

    @classmethod
    def get_by_id(cls, record_id):
        item = cls.dynamodb.get_item(TableName=cls.TABLE_NAME, Key={"id": {"S": record_id}}).get("Item")
        return cls.prepare_loaded_item(item)

    @staticmethod
    def prepare_loaded_item(item):
        if item is None:
            return None

        for key, value in item.items():
            data_type = list(value)[0]
            if key == "http_code":
                item[key] = int(value[data_type])
            else:
                item[key] = value[data_type]
        return item

    @classmethod
    def update_key(cls, record_id, key, new_value):
        data_type = "S"
        if not isinstance(new_value, str):
            if isinstance(new_value, dict) or isinstance(new_value, list):
                new_value = json.dumps(new_value)
            elif isinstance(new_value, bool):
                data_type = "BOOL"
            elif key == "http_code":
                data_type = "N"
                new_value = str(new_value)
            else:
                new_value = str(new_value)

        updated_item = cls.dynamodb.update_item(
            TableName=cls.TABLE_NAME,
            Key={"id": {"S": record_id}},
            UpdateExpression="SET {} = :new_content".format(key),
            ExpressionAttributeValues={":new_content": {data_type: new_value}},
        )
        return updated_item

    @classmethod
    def ensure_table_exists(cls):
        log(INFO, "Ensuring DynamoDB table exists: '{}'.".format(cls.TABLE_NAME))
        try:
            cls.dynamodb.create_table(
                AttributeDefinitions=[
                    {
                        "AttributeName": "id",
                        "AttributeType": "S",
                    },
                    {
                        "AttributeName": "user_id",
                        "AttributeType": "S",
                    },
                ],
                KeySchema=[
                    {
                        "AttributeName": "id",
                        "KeyType": "HASH",
                    },
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "user_id",
                        "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}],
                        "Projection": {"ProjectionType": "ALL"},
                    }
                ],
                TableName=cls.TABLE_NAME,
                BillingMode="PAY_PER_REQUEST",  # we use on-demand pricing
            )
            log(INFO, "Successfully created DynamoDB table '{}'.".format(cls.TABLE_NAME))
        except cls.dynamodb.exceptions.ResourceInUseException:
            log(INFO, "DynamoDB table '{}' already exists, ignoring.".format(cls.TABLE_NAME))

    @classmethod
    def delete_table(cls):
        try:
            # TableName=
            cls.dynamodb.delete_table(TableName=cls.TABLE_NAME)
            log(INFO, "Table {} Successfully deleted.".format(cls.TABLE_NAME))
        except:
            log(INFO, "Table {} does not exists.".format(cls.TABLE_NAME))

    @classmethod
    def clear_table(cls):
        for item in cls.items():
            cls.delete(item["id"])


class JobsPersistence(Persistence):
    TABLE_NAME = TABLE_NAME_PREFIX + "shopeneo_jobs"

    @classmethod
    def create(cls, data):
        """
        Creates a new record and returns its record ID (UUID).
        """
        record_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        item = {
            "id": {"S": record_id},
            "user_id": {"S": data["user_id"]},
            "process": {"S": json.dumps(data["process"])},
            "batch_request_id": {
                "S": data.get("batch_request_id", "null")
            },  # .get and default value is needed because services don't use SH batch
            "previous_batch_request_ids": {"S": json.dumps([])},
            "created": {"S": timestamp},
            "last_updated": {"S": timestamp},
            "error_msg": {"S": str(data.get("error_msg"))},
            "error_code": {"S": str(data.get("error_code"))},
            "http_code": {"N": data.get("http_code", "200")},
            "results": {"S": json.dumps(data.get("results"))},
        }
        if data.get("title"):
            item["title"] = {"S": str(data.get("title"))}
        if data.get("description"):
            item["description"] = {"S": str(data.get("description"))}
        if data.get("plan"):
            item["plan"] = {"S": str(data.get("plan"))}
        if data.get("budget"):
            item["budget"] = {"S": str(data.get("budget"))}

        cls.dynamodb.put_item(
            TableName=cls.TABLE_NAME,
            Item=item,
        )
        return record_id

    @classmethod
    def update_status(cls, job_id, new_value):
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cls.update_key(job_id, "last_updated", timestamp)
        cls.update_key(job_id, "current_status", new_value)

    @classmethod
    def delete(cls, job_id):
        cls.dynamodb.delete_item(TableName=cls.TABLE_NAME, Key={"id": {"S": job_id}})


class ProcessGraphsPersistence(Persistence):
    TABLE_NAME = TABLE_NAME_PREFIX + "shopeneo_process_graphs"

    @classmethod
    def create(cls, data, record_id):
        """
        Creates a new record.
        """
        item = {
            "id": {"S": record_id},
            "user_id": {"S": data["user_id"]},
            "process_graph": {"S": json.dumps(data.get("process_graph"))},
        }
        if data.get("summary"):
            item["summary"] = {"S": str(data.get("summary"))}
        if data.get("description"):
            item["description"] = {"S": str(data.get("description"))}
        if data.get("categories"):
            item["categories"] = {"L": data.get("categories")}
        if data.get("parameters"):
            item["parameters"] = {"L": data.get("parameters")}
        if data.get("returns"):
            item["returns"] = {"M": data.get("returns")}
        if data.get("deprecated") is not None:
            item["deprecated"] = {"BOOL": data.get("deprecated")}
        if data.get("experimental") is not None:
            item["experimental"] = {"BOOL": data.get("experimental")}
        if data.get("exceptions"):
            item["exceptions"] = {"M": data.get("exceptions")}
        if data.get("examples"):
            item["examples"] = {"L": data.get("examples")}
        if data.get("links"):
            item["links"] = {"L": data.get("links")}

        response = cls.dynamodb.put_item(
            TableName=cls.TABLE_NAME,
            Item=item,
        )
        return response


class ServicesPersistence(Persistence):
    TABLE_NAME = TABLE_NAME_PREFIX + "shopeneo_services"

    @classmethod
    def create(cls, data):
        """
        Creates a new record and returns its record ID (UUID).
        """
        record_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        item = {
            "id": {"S": record_id},
            "user_id": {"S": data["user_id"]},
            "service_type": {"S": str(data.get("type"))},
            "process": {"S": json.dumps(data.get("process"))},
            "enabled": {"BOOL": data.get("enabled", True)},
            "configuration": {"S": json.dumps(data.get("configuration"))},
            "created": {"S": timestamp},
        }
        for optional_field in ["title", "description", "plan", "budget"]:
            if data.get(optional_field) is not None:
                item[optional_field] = {"S": str(data.get(optional_field))}

        cls.dynamodb.put_item(
            TableName=cls.TABLE_NAME,
            Item=item,
        )
        return record_id


if __name__ == "__main__":

    # To create tables, run:
    #   $ pipenv shell
    #   <shell> $ DEPLOYMENT_TYPE="production" ./dynamodb.py
    #
    # Currently it is not posible to create tables from the Lambda because the
    # boto3 version included is too old, and we can't upload newer one (creating
    # tables doesn't work if we do that)

    log(
        INFO,
        "Initializing DynamoDB (url: {}, production: {})...".format(
            DYNAMODB_LOCAL_URL, DEPLOYMENT_TYPE == DeploymentTypes.PRODUCTION
        ),
    )
    JobsPersistence.ensure_table_exists()
    ProcessGraphsPersistence.ensure_table_exists()
    ServicesPersistence.ensure_table_exists()
    log(INFO, "DynamoDB initialized.")
