import os
import json
import shutil

from processing.const import ShBatchResponseOutput, ProcessingRequestTypes
from processing.processing import new_process
from post_processing.gtiff_parser import parse_multitemporal_gtiff_to_format
from post_processing.const import TMP_FOLDER, parsed_output_file_name


def check_if_already_parsed(results, output_format):
    for result in results:
        if (
            parsed_output_file_name[output_format]["name"] in result["Key"]
            and parsed_output_file_name[output_format]["ext"] in result["Key"]
        ):
            return True

    return False

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


def upload_output_to_bucket(local_file_paths, bucket):
    for path in local_file_paths:
        s3_path = path[len(f"{TMP_FOLDER}") :]
        bucket.upload_file_to_bucket(path, None, s3_path)


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
        batch_request_dir = f"{TMP_FOLDER}{batch_request_id}"
        batch_subfolder = f"{batch_request_dir}/{subfolder_id}/"
        if os.path.exists(batch_request_dir):
            shutil.rmtree(batch_request_dir)
        os.makedirs(batch_subfolder)

        output_file_paths = parse_multitemporal_gtiff_to_format(
            input_tiff, input_metadata, batch_subfolder, parsed_output_file_name[output_format], output_format
        )
        upload_output_to_bucket(output_file_paths, bucket)

        # remove folder after the folder/file has been uploaded
        shutil.rmtree(batch_request_dir)
