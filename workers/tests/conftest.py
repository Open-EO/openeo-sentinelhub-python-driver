import os

def pytest_sessionstart(session):
    os.environ["DATA_AWS_S3_ENDPOINT_URL"] = "http://localhost:9000"
    os.environ["SENTINELHUB_INSTANCE_ID"] = "fake_sentinel_hub_instance_id"
    os.environ["SENTINELHUB_LAYER_ID_S2L1C"] = "S2L1C"
    os.environ["SENTINELHUB_LAYER_ID_S1GRD"] = "S1GRDIW"