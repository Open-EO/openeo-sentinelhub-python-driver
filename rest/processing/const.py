from enum import Enum

from sentinelhub import MimeType, SentinelHubBatch


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


class OpenEOOrderStatus(Enum):
    ORDERABLE = "orderable"
    ORDERED = "ordered"
    SHIPPING = "shipping"
    DELIVERED = "delivered"
    UNABLE_TO_DELIVER = "unable_to_deliver"
    CANCELED = "canceled"

    @staticmethod
    def from_sentinelhub_order_status(sentinelhub_order_status):
        conversion_table = {
            "CREATED": OpenEOOrderStatus.ORDERABLE,
            "RUNNING": OpenEOOrderStatus.ORDERED,
            "DONE": OpenEOOrderStatus.DELIVERED,
            "PARTIAL": OpenEOOrderStatus.UNABLE_TO_DELIVER,
            "FAILED": OpenEOOrderStatus.UNABLE_TO_DELIVER,
            "CANCELLED": OpenEOOrderStatus.CANCELED,
        }
        return conversion_table.get(sentinelhub_order_status)
