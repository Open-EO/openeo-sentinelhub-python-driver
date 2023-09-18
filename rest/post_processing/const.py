from sentinelhub import MimeType
from processing.const import CustomMimeType

TMP_FOLDER = "/tmp/"

parsed_output_file_name = {
    MimeType.TIFF: {"name": "output", "ext": ".tif"},
    CustomMimeType.ZARR: {"name": "output", "ext": ".zarr"},
    CustomMimeType.NETCDF: {"name": "output", "ext": ".nc"},
}
