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
    if len(time_dimensions) > 1:
        raise Internal("More than 1 time dimension exist. Only 0 or 1 time dimension is supported.")

    if len(bands_dimensions) > 1:
        raise Internal("More than 1 bands dimension exist. Only 0 or 1 bands dimension is supported.")


def get_timestamps_arrays(datacube_time_as_bands, time_dimensions, bands_dimensions, output_format):
    bands_dimension = bands_dimensions[0] if len(bands_dimensions) > 0 else None
    time_dimension = time_dimensions[0] if len(time_dimensions) > 0 else None

    num_of_img_bands = len(datacube_time_as_bands["band"])
    num_of_band_labels = len(bands_dimension["labels"]) if bands_dimension else 1
    num_of_time_labels = len(time_dimension["labels"]) if time_dimension else 1
    num_of_usable_img_bands = num_of_time_labels * num_of_band_labels

    if num_of_img_bands < num_of_usable_img_bands:
        raise Internal(f"Datacube dimensions not compatible with returned image.")

    list_of_timestamps = []
    list_of_timestamp_arrays = []

    for i in range(0, num_of_usable_img_bands, num_of_band_labels):
        date = time_dimension["labels"][int(i / num_of_band_labels)] if time_dimension else None
        timestamp_array = datacube_time_as_bands[i : i + num_of_band_labels]

        # datacube_time_as_bands of type xarray DataArray already has bands dimension, we need to
        # - update its labels or remove it
        # - add time dimension and its labels
        if output_format in [CustomMimeType.NETCDF, CustomMimeType.ZARR]:
            if bands_dimension:
                timestamp_array = timestamp_array.assign_coords(band=bands_dimension["labels"])
            else:
                timestamp_array = timestamp_array.drop_vars("band")
            if time_dimension:
                timestamp_array = timestamp_array.assign_coords(t=pd.to_datetime(parser.parse(date)))
                timestamp_array = timestamp_array.expand_dims(dim="t")

        list_of_timestamps.append(date)
        list_of_timestamp_arrays.append(timestamp_array)

    return list_of_timestamps, list_of_timestamp_arrays


def save_as_gtiff(list_of_timestamps, list_of_timestamp_arrays, output_dir, output_name):
    output_file_paths = []
    for array, date in zip(list_of_timestamp_arrays, list_of_timestamps):
        date_string = f"_{date}" if date else ""
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
