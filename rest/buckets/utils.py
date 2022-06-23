import os
import warnings

from const import SentinelhubDeployments
from utils import get_env_var
from .results_bucket import ResultsBucket, CreodiasResultsBucket


BUCKET_NAMES = {
    SentinelhubDeployments.MAIN: get_env_var("RESULTS_S3_BUCKET_NAME_MAIN"),
    SentinelhubDeployments.CREODIAS: get_env_var("RESULTS_S3_BUCKET_NAME_CREODIAS"),
    SentinelhubDeployments.USWEST: get_env_var("RESULTS_S3_BUCKET_NAME_USWEST"),
}

BUCKET_REGION_NAMES = {
    SentinelhubDeployments.MAIN: "eu-central-1",
    SentinelhubDeployments.CREODIAS: "RegionOne",
    SentinelhubDeployments.USWEST: "us-west-2",
}

BUCKET_ENDPOINT_URLS = {
    SentinelhubDeployments.MAIN: None,
    SentinelhubDeployments.CREODIAS: "https://s3.waw2-1.cloudferro.com",
    SentinelhubDeployments.USWEST: None,
}

BUCKET_ACCESS_KEY_IDS = {
    SentinelhubDeployments.MAIN: get_env_var("RESULTS_S3_BUCKET_ACCESS_KEY_ID_MAIN"),
    SentinelhubDeployments.CREODIAS: get_env_var("RESULTS_S3_BUCKET_ACCESS_KEY_ID_CREODIAS"),
    SentinelhubDeployments.USWEST: get_env_var("RESULTS_S3_BUCKET_ACCESS_KEY_ID_USWEST"),
}

BUCKET_SECRET_ACCESS_KEYS = {
    SentinelhubDeployments.MAIN: get_env_var("RESULTS_S3_BUCKET_SECRET_ACCESS_KEY_MAIN"),
    SentinelhubDeployments.CREODIAS: get_env_var("RESULTS_S3_BUCKET_SECRET_ACCESS_KEY_CREODIAS"),
    SentinelhubDeployments.USWEST: get_env_var("RESULTS_S3_BUCKET_SECRET_ACCESS_KEY_USWEST"),
}


def get_bucket(deployment_endpoint):
    bucket_name = BUCKET_NAMES[deployment_endpoint]
    region_name = BUCKET_REGION_NAMES[deployment_endpoint]
    endpoint_url = BUCKET_ENDPOINT_URLS[deployment_endpoint]
    access_key_id = BUCKET_ACCESS_KEY_IDS[deployment_endpoint]
    secret_access_key = BUCKET_SECRET_ACCESS_KEYS[deployment_endpoint]
    if deployment_endpoint == SentinelhubDeployments.CREODIAS:
        return CreodiasResultsBucket(bucket_name, region_name, endpoint_url, access_key_id, secret_access_key)
    return ResultsBucket(bucket_name, region_name, endpoint_url, access_key_id, secret_access_key)
