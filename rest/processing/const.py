from enum import Enum

from sentinelhub import MimeType


class ShBatchResponseOutput(Enum):
    DATA = "default"
    METADATA = "userdata"


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
}

supported_sample_types = {
    MimeType.PNG: [SampleType.UINT8, SampleType.UINT16],
    MimeType.JPG: [SampleType.UINT8],
    MimeType.TIFF: [SampleType.UINT8, SampleType.UINT16, SampleType.FLOAT32],
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
        # "zarr": MimeType.TIFF,
        # "netcdf": MimeType.TIFF,
    },
    ProcessingRequestTypes.SYNC: {
        "gtiff": MimeType.TIFF,
        "png": MimeType.PNG,
        "jpeg": MimeType.JPG,
    },
}

supported_mime_types_error_msg = {
    ProcessingRequestTypes.BATCH: "Currently supported format is GTIFF.",
    ProcessingRequestTypes.SYNC: "Currently supported formats are GTIFF, PNG and JPEG",
}
