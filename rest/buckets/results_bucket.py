import boto3


class ResultsBucket:
    def __init__(self, bucket_name, region_name, endpoint_url, access_key_id, secret_access_key):
        self.bucket_name = bucket_name
        self.client = s3 = boto3.client(
            "s3",
            region_name=region_name,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

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
            results.extend(response["Contents"])
            if response["IsTruncated"]:
                continuation_token = response["NextContinuationToken"]
            else:
                break

        return results

    def delete_objects(self, object_keys_to_delete):
        self.client.delete_objects(Bucket=self.bucket_name, Delete=object_keys_to_delete)

    def generate_presigned_url(self, object_key=None):
        return self.client.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": object_key,
            },
        )
