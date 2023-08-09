from enum import Enum
import mimetypes

from sentinelhub import MimeType


class TilingGridUnit(Enum):
    DEGREE = "DEGREE"
    METRE = "METRE"


# inspired by sentinelhub.py MimeType class
# https://github.com/sentinel-hub/sentinelhub-py/blob/master/sentinelhub/constants.py#L261
class CustomMimeType(Enum):
    ZARR = "zarr"

    # this method is needed because mimetype.get_string() is called in construct_output in rest/processing/sentinel_hub.py
    def get_string(self) -> str:
        # mimetype string should be `zarr/array` for ZARR
        # https://docs.sentinel-hub.com/api/latest/reference/#tag/batch_process/operation/createNewBatchProcessingRequest
        if self is CustomMimeType.ZARR:
            return "zarr/array"
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
}

supported_sample_types = {
    MimeType.PNG: [SampleType.UINT8, SampleType.UINT16],
    MimeType.JPG: [SampleType.UINT8],
    MimeType.TIFF: [SampleType.UINT8, SampleType.UINT16, SampleType.FLOAT32],
    CustomMimeType.ZARR: [SampleType.UINT8, SampleType.UINT16, SampleType.FLOAT32],
}

sample_types_to_bytes = {
    SampleType.UINT8: 1,
    SampleType.UINT16: 2,
    SampleType.FLOAT32: 4,
}

sample_type_to_zarr_dtype = {
    SampleType.UINT8: "|u1",
    SampleType.UINT16: "<u2",
    SampleType.FLOAT32: "<f8",
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
    },
    ProcessingRequestTypes.SYNC: {
        "gtiff": MimeType.TIFF,
        "png": MimeType.PNG,
        "jpeg": MimeType.JPG,
    },
}

supported_mime_types_error_msg = {
    ProcessingRequestTypes.BATCH: "Currently only GTIFF and ZARR are supported.",
    ProcessingRequestTypes.SYNC: "Currently supported formats are GTIFF, PNG or JPEG",
}
