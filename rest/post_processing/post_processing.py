import os
import json
import shutil

from processing.const import ShBatchResponseOutput, ProcessingRequestTypes
from processing.processing import new_process
from post_processing.gtiff_parser import parse_multitemporal_gtiff_to_netcdf_zarr


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


def upload_output_to_bucket(local_file_path, bucket, s3_prefix, s3_file_name):
    print("upload output", local_file_path, bucket, s3_prefix, s3_file_name)

    if os.path.isdir(local_file_path):
        for root, dirs, files in os.walk(local_file_path):
            for file in files:
                print("file:", os.path.join(root, file))
    elif os.path.isfile(local_file_path):
        print("file:", local_file_path)

    # remove folder after the folder/file has been uploaded
    # shutil.rmtree( f"/tmp/{s3_prefix}")


def parse_sh_gtiff_to_format(job, bucket):
    results = bucket.get_data_from_bucket(prefix=job["batch_request_id"])

    process = new_process(json.loads(job["process"]), request_type=ProcessingRequestTypes.BATCH)
    output_format = process.get_mimetype()
    print(output_format)

    subfolder_groups = generate_subfolder_groups(job["batch_request_id"], bucket, results)

    for subfolder_id, subfolder_group in subfolder_groups.items():
        # print(subfolder_id)
        input_tiff = subfolder_group[ShBatchResponseOutput.DATA.value]
        input_metadata = subfolder_group[ShBatchResponseOutput.METADATA.value]

        # preventively remove directory and create it again
        output_dir = f"/tmp/{subfolder_id}"
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.mkdir(output_dir)

        output_file_path, output_file_name = parse_multitemporal_gtiff_to_netcdf_zarr(
            input_tiff, input_metadata, output_dir, output_format
        )
        print("path", output_file_path, output_file_name)

        upload_output_to_bucket(output_file_path, bucket, subfolder_id, output_file_name)
