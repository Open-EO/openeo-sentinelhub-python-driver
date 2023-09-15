import os
import shutil
# import json
import rioxarray
from dateutil import parser
import pandas as pd
import xarray as xr
import requests

from processing.const import CustomMimeType
from openeoerrors import Internal


def parse_multitemporal_gtiff_to_netcdf_zarr(input_tiff, input_metadata, output_dir, output_format):
    datacube_time_as_bands = rioxarray.open_rasterio(input_tiff)

    # for local use:
    # with open(input_metadata) as metadata_file:
    #     datacube_metadata = json.load(metadata_file)

    datacube_metadata = requests.get(input_metadata).json()

    # assume it's only 1 time and 1 bands dimension
    time_dimensions = [dim for dim in datacube_metadata["outputDimensions"] if dim["type"] == "temporal"]
    bands_dimensions = [dim for dim in datacube_metadata["outputDimensions"] if dim["type"] == "bands"]

    if len(time_dimensions) == 0:
        print("time dimension does not exist")
        return

    if len(time_dimensions) > 1:
        print("more than 1 time dimensions")
        return

    if len(bands_dimensions) == 0:
        print("bands dimension does not exist")
        return

    if len(bands_dimensions) > 1:
        print("more than 1 bands dimensions")
        return

    num_of_img_bands = len(datacube_time_as_bands["band"])
    num_of_bands_dimension = len(bands_dimensions[0]["labels"])

    list_of_timestamp_arrays = []

    for i in range(0, num_of_img_bands, num_of_bands_dimension):
        date = time_dimensions[0]["labels"][int(i / num_of_bands_dimension)]
        parsed_time = parser.parse(date)
        pandas_time = pd.to_datetime(parsed_time)

        timestamp_array = datacube_time_as_bands[i : i + num_of_bands_dimension]
        timestamp_array = timestamp_array.assign_coords(band=bands_dimensions[0]["labels"])
        timestamp_array = timestamp_array.assign_coords(t=pandas_time)
        timestamp_array = timestamp_array.expand_dims(dim="t")

        list_of_timestamp_arrays.append(timestamp_array)

    datacube_with_time_dimension = xr.combine_by_coords(list_of_timestamp_arrays)

    if output_format == CustomMimeType.NETCDF:
        datacube_with_time_dimension.to_netcdf(os.path.join(output_dir, "output.nc"))
    elif output_format == CustomMimeType.ZARR:
        datacube_with_time_dimension.to_zarr(os.path.join(output_dir, "output.zarr"))
    else:
        raise Internal(f"Parsing to format {output_format} is not supported")

    # remove folder after the folder/file has been uploaded
    # shutil.rmtree(output_dir)


# parse_multitemporal_gtiff_to_netcdf_zarr(
#     input_tiff="demo_data/input/default.tiff",
#     input_metadata="demo_data/input/userdata.json",
#     output_dir="/tmp/parse_gtiff",
#     output_format="netcdf",
# )
