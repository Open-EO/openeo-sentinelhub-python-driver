import boto3
from botocore.client import Config


class ResultsBucket:
    def __init__(self, bucket_name, region_name, endpoint_url, access_key_id, secret_access_key):
        self.bucket_name = bucket_name
        self.client = s3 = boto3.client(
            "s3",
            region_name=region_name,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(signature_version="s3v4"),
        )

    def put_file_to_bucket(self, content_as_string, prefix=None, file_name="file"):
        file_path = prefix + "/" + file_name if prefix else file_name

        self.client.put_object(Bucket=self.bucket_name, Key=file_path, Body=content_as_string)

    def upload_file_to_bucket(self, local_file_path, prefix=None, file_name="file"):
        s3_file_path = prefix + "/" + file_name if prefix else file_name

        self.client.upload_file(local_file_path, self.bucket_name, s3_file_path)

    def get_data_from_bucket(self, prefix=None):
        continuation_token = None
        results = []

        while True:
            if continuation_token:
                response = self.client.list_objects_v2(
                    Bucket=self.bucket_name, Prefix=prefix, ContinuationToken=continuation_token
                )
            else:
                response = self.client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            if response.get("Contents"):
                results.extend(response["Contents"])
            if response["IsTruncated"]:
                continuation_token = response["NextContinuationToken"]
            else:
                break

        return results

    def delete_objects(self, objects_to_delete):
        if len(objects_to_delete) == 0:
            return
        object_keys_to_delete = {"Objects": [{"Key": obj["Key"]} for obj in objects_to_delete]}
        self.client.delete_objects(Bucket=self.bucket_name, Delete=object_keys_to_delete)

    def generate_presigned_url(self, object_key=None):
        return self.client.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": object_key,
            },
            ExpiresIn=604800,  # equals 7 days, part of federation agreement
        )


class CreodiasResultsBucket(ResultsBucket):
    def __init__(self, bucket_name, region_name, endpoint_url, access_key_id, secret_access_key):
        super().__init__(bucket_name, region_name, endpoint_url, access_key_id, secret_access_key)
        self.bucket_name = self.bucket_name[
            self.bucket_name.find(":") + 1 :
        ]  # Bucket name is in format <project-id>:<bucket-name>, but boto3 requires only <bucket-name> part
