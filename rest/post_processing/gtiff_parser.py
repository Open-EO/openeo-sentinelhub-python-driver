import os
import shutil
import rioxarray
from dateutil import parser
import pandas as pd
import xarray as xr
import requests
from sentinelhub import MimeType

from processing.const import CustomMimeType
from openeoerrors import Internal

import json

# assume it's only 1 time and 1 bands dimension
def check_dimensions(time_dimensions, bands_dimensions):
    if len(time_dimensions) == 0:
        print("No time dimensions exist. Only 1 time dimension is supported.")
        # raise Internal("No time dimensions exist. Only 1 time dimension is supported.")

    if len(time_dimensions) > 1:
        raise Internal("More than 1 time dimension exist. Only 1 time dimension is supported.")

    if len(bands_dimensions) == 0:
        raise Internal("No bands dimensions exist. Only 1 bands dimension is supported.")

    if len(bands_dimensions) > 1:
        raise Internal("More than 1 bands dimension exist. Only 1 bands dimension is supported.")


def get_timestamps_arrays(datacube_time_as_bands, time_dimensions, bands_dimensions, output_format):
    num_of_img_bands = len(datacube_time_as_bands["band"])
    num_of_bands_dimension = len(bands_dimensions[0]["labels"])

    num_time_labels = 0
    for time_dim in time_dimensions:
        num_time_labels += len(time_dim["labels"])
    
    num_band_labels = 0
    for band_dim in bands_dimensions:
        num_band_labels += len(band_dim["labels"])

    num_actual_img_bands = (num_time_labels or 1) * (num_band_labels or 1)

    list_of_timestamps = []
    list_of_timestamp_arrays = []

    printdata = {
        "data": datacube_time_as_bands,
        "data_length": len(datacube_time_as_bands),
        "data_len/num_of_bands_dimension": len(datacube_time_as_bands) / num_of_bands_dimension,
        "bands_dimensions": bands_dimensions,
        "time_dimensions": time_dimensions,
        "num_img_bands": num_of_img_bands, 
        "num_bands_dim": num_of_bands_dimension, 
        "range": range(0, num_actual_img_bands, num_of_bands_dimension),
        "num_actual_img_bands": num_actual_img_bands,
        "num_band_labels": num_band_labels,
        "num_time_labels": num_time_labels,
    }

    print("get_timestamps_arrays")
    print(json.dumps(printdata, sort_keys=True, indent=4, default=str))

    for i in range(0, num_actual_img_bands, num_of_bands_dimension):

        print("for loop", {
            "time_dims": time_dimensions, 
            "time_dim_index": int(i / num_of_bands_dimension)
        })


        date = time_dimensions[0]["labels"][int(i / num_of_bands_dimension)] if num_time_labels > 0 else ""
        timestamp_array = datacube_time_as_bands[i : i + num_of_bands_dimension]

        if output_format in [CustomMimeType.NETCDF, CustomMimeType.ZARR]:
            timestamp_array = timestamp_array.assign_coords(band=bands_dimensions[0]["labels"])
            if num_time_labels > 0:
                timestamp_array = timestamp_array.assign_coords(t=pd.to_datetime(parser.parse(date)))
                timestamp_array = timestamp_array.expand_dims(dim="t")

        list_of_timestamps.append(date)
        list_of_timestamp_arrays.append(timestamp_array)

    return list_of_timestamps, list_of_timestamp_arrays


def save_as_gtiff(list_of_timestamps, list_of_timestamp_arrays, output_dir, output_name):
    output_file_paths = []
    for array, date in zip(list_of_timestamp_arrays, list_of_timestamps):
        date_string = "" if date == "" else f"_{date}"
        file_name = f"{output_name['name']}{date_string}{output_name['ext']}"
        file_path = os.path.join(output_dir, file_name)
        output_file_paths.append(file_path)

        array.rio.to_raster(
            file_path,
            tiled=True,  # GDAL: By default striped TIFF files are created. This option can be used to force creation of tiled TIFF files.
            windowed=True,  # rioxarray: read & write one window at a time
        )
    return output_file_paths


def save_as_netcdf(list_of_timestamp_arrays, output_dir, output_name):
    datacube_with_time_dimension = xr.combine_by_coords(list_of_timestamp_arrays)
    output_file_path = os.path.join(output_dir, f"{output_name['name']}{output_name['ext']}")
    datacube_with_time_dimension.to_netcdf(output_file_path)
    return [output_file_path]


def save_as_zarr(list_of_timestamp_arrays, output_dir, output_name):
    datacube_with_time_dimension = xr.combine_by_coords(list_of_timestamp_arrays)
    output_file_path = os.path.join(output_dir, f"{output_name['name']}{output_name['ext']}")
    datacube_with_time_dimension.to_zarr(output_file_path)
    # zip the zarr folder to avoid listing a bunch of files
    shutil.make_archive(output_file_path, "zip", output_file_path)
    output_file_path = f"{output_file_path}.zip"
    return [output_file_path]


def parse_multitemporal_gtiff_to_format(input_tiff, input_metadata, output_dir, output_name, output_format):
    datacube_time_as_bands = rioxarray.open_rasterio(input_tiff)
    datacube_metadata = requests.get(input_metadata).json()

    time_dimensions = [dim for dim in datacube_metadata["outputDimensions"] if dim["type"] == "temporal"]
    bands_dimensions = [dim for dim in datacube_metadata["outputDimensions"] if dim["type"] == "bands"]

    # mock a bands dimension (with 1 band) if it's not present in the data
    # e.g. save_result process right after ndvi process which doesn't have a target band set
    if len(bands_dimensions) == 0:
        bands_dimensions = [{"name": "bands", "type": "bands", "labels": ["results"]}]

    # if len(time_dimensions) == 0:
    #     time_dimensions = [{"name": "t", "type": "temporal", "labels": [""]}]

    check_dimensions(time_dimensions, bands_dimensions)

    list_of_timestamps, list_of_timestamp_arrays = get_timestamps_arrays(
        datacube_time_as_bands, time_dimensions, bands_dimensions, output_format
    )

    if output_format == MimeType.TIFF:
        return save_as_gtiff(list_of_timestamps, list_of_timestamp_arrays, output_dir, output_name)

    if output_format == CustomMimeType.NETCDF:
        return save_as_netcdf(list_of_timestamp_arrays, output_dir, output_name)

    if output_format == CustomMimeType.ZARR:
        return save_as_zarr(list_of_timestamp_arrays, output_dir, output_name)

    raise Internal(f"Parsing to format {output_format} is not supported")
