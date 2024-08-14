from enum import Enum
import mimetypes
from sentinelhub import MimeType


class ShBatchResponseOutput(Enum):
    DATA = "default"
    METADATA = "userdata"


# Driver needs a way to save the originally requested format in the Process class so that
# the post-processing can parse geotiff from Sentinel Hub to the correct format.
# inspired by sentinelhub.py MimeType class
# https://github.com/sentinel-hub/sentinelhub-py/blob/master/sentinelhub/constants.py#L261
class CustomMimeType(Enum):
    ZARR = "zarr"
    NETCDF = "netcdf"

    # This method is needed because mimetype.get_string() is called in construct_output() in rest/processing/sentinel_hub.py
    def get_string(self) -> str:
        # Need to get geotiff from Sentinel Hub (parsing to the correct format is done in post-processing)
        if self is CustomMimeType.ZARR or self is CustomMimeType.NETCDF:
            return MimeType.TIFF.get_string()
        return mimetypes.types_map["." + self.value]


class SampleType(Enum):
    AUTO = "AUTO"
    UINT8 = "UINT8"
    UINT16 = "UINT16"
    FLOAT32 = "FLOAT32"

    @staticmethod
    def from_gdal_datatype(gdal_datatype):
        gdal_datatype = gdal_datatype.lower()
        conversion_table = {
            "byte": SampleType.UINT8,
            "uint16": SampleType.UINT16,
            "float32": SampleType.FLOAT32,
        }
        return conversion_table.get(gdal_datatype)


default_sample_type_for_mimetype = {
    MimeType.PNG: SampleType.UINT8,
    MimeType.JPG: SampleType.UINT8,
    MimeType.TIFF: SampleType.FLOAT32,
    CustomMimeType.ZARR: SampleType.FLOAT32,
    CustomMimeType.NETCDF: SampleType.FLOAT32,
}

supported_sample_types = {
    MimeType.PNG: [SampleType.UINT8, SampleType.UINT16],
    MimeType.JPG: [SampleType.UINT8],
    MimeType.TIFF: [SampleType.UINT8, SampleType.UINT16, SampleType.FLOAT32],
    CustomMimeType.ZARR: [SampleType.UINT8, SampleType.UINT16, SampleType.FLOAT32],
    CustomMimeType.NETCDF: [SampleType.UINT8, SampleType.UINT16, SampleType.FLOAT32],
}

sample_types_to_bytes = {
    SampleType.UINT8: 1,
    SampleType.UINT16: 2,
    SampleType.FLOAT32: 4,
}


class ProcessingRequestTypes(Enum):
    BATCH = "batch"
    SYNC = "sync"

    def get_supported_mime_types(self):
        return supported_mime_types[self]

    def get_unsupported_mimetype_message(self):
        return supported_mime_types_error_msg[self]


supported_mime_types = {
    ProcessingRequestTypes.BATCH: {
        "gtiff": MimeType.TIFF,
        "zarr": CustomMimeType.ZARR,
        "netcdf": CustomMimeType.NETCDF,
    },
    ProcessingRequestTypes.SYNC: {
        "gtiff": MimeType.TIFF,
        "png": MimeType.PNG,
        "jpeg": MimeType.JPG,
    },
}

supported_mime_types_error_msg = {
    ProcessingRequestTypes.BATCH: "Currently supported formats for batch processing jobs are GTIFF, NETCDF and ZARR.",
    ProcessingRequestTypes.SYNC: "Currently supported formats for synchronous processing jobs are GTIFF, PNG and JPEG.",
}

SH_PU_TO_PLATFORM_CREDIT_CONVERSION_RATE = 0.15  # platform credits === SH PU's * 0.15
