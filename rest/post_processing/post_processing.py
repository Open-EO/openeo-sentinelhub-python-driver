import json

from processing.const import ShBatchResponseOutput, ProcessingRequestTypes
from processing.processing import new_process
from post_processing.gtiff_parser import parse_multitemporal_gtiff_to_netcdf_zarr


def parse_sh_gtiff_to_format(job, bucket):
    results = bucket.get_data_from_bucket(prefix=job["batch_request_id"])

    pp = new_process(json.loads(job["process"]), request_type=ProcessingRequestTypes.BATCH)
    print(pp.get_mimetype())

    subfolder_groups = generate_subfolder_groups(job["batch_request_id"], bucket, results)

    for subfolder_id in subfolder_groups:
        # print(subfolder_id)
        input_tiff = subfolder_groups[subfolder_id][ShBatchResponseOutput.DATA.value]
        input_metadata = subfolder_groups[subfolder_id][ShBatchResponseOutput.METADATA.value]
        output_dir = f"/tmp/{subfolder_id}"
        output_format = pp.get_mimetype()
        parse_multitemporal_gtiff_to_netcdf_zarr(input_tiff, input_metadata, output_dir, output_format)


def generate_subfolder_groups(batch_request_id, bucket, results):
    data_metadata_pairs = {}
    for result in results:
        for output in [ShBatchResponseOutput.DATA, ShBatchResponseOutput.METADATA]:
            if output.value in result["Key"]:
                url = bucket.generate_presigned_url(object_key=result["Key"])
                pair_key = result["Key"].replace(f"{batch_request_id}", "").replace("/", "").split(output.value)[0]
                if pair_key not in data_metadata_pairs:
                    data_metadata_pairs[pair_key] = {}
                data_metadata_pairs[pair_key][output.value] = url

    return data_metadata_pairs
