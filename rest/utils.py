import os


def get_data_from_bucket(s3, bucket_name, batch_request_id):
    continuation_token = None
    results = []

    while True:
        if continuation_token:
            response = s3.list_objects_v2(
                Bucket=bucket_name, Prefix=batch_request_id, ContinuationToken=continuation_token
            )
        else:
            response = s3.list_objects_v2(Bucket=bucket_name, Prefix=batch_request_id)
        results.extend(response["Contents"])
        if response["IsTruncated"]:
            continuation_token = response["NextContinuationToken"]
        else:
            break

    return results
