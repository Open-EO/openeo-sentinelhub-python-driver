import os
import json
import shutil

from openeoerrors import Internal
from processing.const import CustomMimeType, ShBatchResponseOutput, ProcessingRequestTypes
from processing.processing import new_process
from post_processing.gtiff_parser import parse_multitemporal_gtiff_to_netcdf_zarr
from post_processing.const import TMP_FOLDER, parsed_output_file_name


def check_if_already_parsed(results, output_format):
    for result in results:
        if parsed_output_file_name[output_format] in result["Key"]:
            return True


def generate_subfolder_groups(batch_request_id, bucket, results):
    subfolder_groups = {}
    for result in results:
        for output in [ShBatchResponseOutput.DATA, ShBatchResponseOutput.METADATA]:
            if output.value in result["Key"]:
                url = bucket.generate_presigned_url(object_key=result["Key"])
                subfolder_name = (
                    result["Key"].replace(f"{batch_request_id}", "").replace("/", "").split(output.value)[0]
                )
                if subfolder_name not in subfolder_groups:
                    subfolder_groups[subfolder_name] = {}
                subfolder_groups[subfolder_name][output.value] = url

    return subfolder_groups


def upload_output_to_bucket(local_file_path, bucket, output_format):
    if output_format == CustomMimeType.NETCDF:
        s3_path = local_file_path[len(f"{TMP_FOLDER}") :]
        bucket.put_file_to_bucket(local_file_path, None, s3_path)
    elif output_format == CustomMimeType.ZARR:
        for root, dirs, files in os.walk(local_file_path):
            for file in files:
                s3_path = os.path.join(root, file)[len(f"{TMP_FOLDER}") :]
                bucket.put_file_to_bucket(file, None, s3_path)
    else:
        raise Internal(f"Unknown output format: {output_format}")

    # remove folder after the folder/file has been uploaded
    # shutil.rmtree( f"/tmp/{s3_prefix}")


def parse_sh_gtiff_to_format(job, bucket):
    batch_request_id = job["batch_request_id"]
    results = bucket.get_data_from_bucket(prefix=batch_request_id)

    process = new_process(json.loads(job["process"]), request_type=ProcessingRequestTypes.BATCH)
    output_format = process.get_mimetype() 

    if check_if_already_parsed(results, output_format):
        return

    subfolder_groups = generate_subfolder_groups(batch_request_id, bucket, results)

    for subfolder_id, subfolder_group in subfolder_groups.items():
        input_tiff = subfolder_group[ShBatchResponseOutput.DATA.value]
        input_metadata = subfolder_group[ShBatchResponseOutput.METADATA.value]

        # preventively remove directory and create it again
        batch_output_dir = f"{batch_request_id}/{subfolder_id}"
        tmp_dir = f"{TMP_FOLDER}{batch_output_dir}"
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
        os.makedirs(tmp_dir)

        output_file_path = parse_multitemporal_gtiff_to_netcdf_zarr(input_tiff, input_metadata, tmp_dir, output_format)
        upload_output_to_bucket(output_file_path, bucket, output_format)
