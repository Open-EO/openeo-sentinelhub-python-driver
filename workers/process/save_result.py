import os
from datetime import datetime, timedelta
from collections import namedtuple
from osgeo import gdal, osr
import boto3
import numpy as np
import json


from ._common import ProcessEOTask, StorageFailure, ProcessParameterInvalid, DimensionType, DataCube
import process


S3_BUCKET_NAME = "com.sinergise.openeo.results"
FAKE_AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
FAKE_AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


AWS_PRODUCTION = os.environ.get("AWS_PRODUCTION", "").lower() in ["true", "1", "yes"]
DATA_AWS_ACCESS_KEY_ID = os.environ.get("DATA_AWS_ACCESS_KEY_ID", FAKE_AWS_ACCESS_KEY_ID)
DATA_AWS_SECRET_ACCESS_KEY = os.environ.get("DATA_AWS_SECRET_ACCESS_KEY", FAKE_AWS_SECRET_ACCESS_KEY)
DATA_AWS_REGION = os.environ.get("DATA_AWS_REGION", "eu-central-1")
DATA_AWS_S3_ENDPOINT_URL = os.environ.get("DATA_AWS_S3_ENDPOINT_URL", "http://localhost:9000")


OutputFormat = namedtuple("OutputFormat", "ext mime_type default_datatype")
OUTPUT_FORMATS = {
    "gtiff": OutputFormat("tiff", "image/tiff; application=geotiff", "uint16"),
    "png": OutputFormat("png", "image/png", "uint16"),
    "jpeg": OutputFormat("jpeg", "image/jpeg", "byte"),
    "json": OutputFormat("json", "application/json", None),
}


def serialize_data(data):
    temporal_dims = [d for d in data.dims if data.coords[d].dtype.type == np.datetime64]
    for dim in temporal_dims:
        data = data.assign_coords({dim: data[dim].coords.to_index().strftime("%Y-%m-%dT%H-%M-%S").tolist()})
    band_dims = data.get_dims_of_type(DimensionType.BANDS)
    for dim in band_dims:
        new_band_labels = []
        for band in data.coords[dim].values:
            new_band_labels.append(band.__dict__)
        data = data.assign_coords({dim: new_band_labels})
    if "bbox" in data.attrs:
        bbox = data.attrs["bbox"]
        xmin, ymin = bbox.lower_left
        xmax, ymax = bbox.upper_right
        crs = str(bbox._crs)
        data.attrs["bbox"] = {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax, "crs": crs}
    # replace nan, inf and -inf with None:
    data = data.where(np.isfinite(data.data), None)
    return data.to_dict()


class save_resultEOTask(ProcessEOTask):
    _s3 = (
        boto3.client(
            "s3",
            region_name=DATA_AWS_REGION,
            aws_access_key_id=DATA_AWS_ACCESS_KEY_ID,
            aws_secret_access_key=DATA_AWS_SECRET_ACCESS_KEY,
        )
        if AWS_PRODUCTION
        else boto3.client(
            "s3",
            endpoint_url=DATA_AWS_S3_ENDPOINT_URL,
            region_name=DATA_AWS_REGION,
            aws_access_key_id=DATA_AWS_ACCESS_KEY_ID,
            aws_secret_access_key=DATA_AWS_SECRET_ACCESS_KEY,
        )
    )
    GDAL_DATATYPES = {
        "byte": gdal.GDT_Byte,
        "uint16": gdal.GDT_UInt16,
        "int16": gdal.GDT_Int16,
        "uint32": gdal.GDT_UInt32,
        "int32": gdal.GDT_Int32,
        "float32": gdal.GDT_Float32,
        "float64": gdal.GDT_Float64,
        "cint16": gdal.GDT_CInt16,
        "cint32": gdal.GDT_CInt32,
        "cfloat32": gdal.GDT_CFloat32,
        "cfloat64": gdal.GDT_CFloat64,
    }

    def _put_file_to_s3(self, filename, mime_type, body=None):
        object_key = "{}/{}".format(self.job_id, os.path.basename(filename))
        if body is None:
            body = open(filename, "rb")
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_object
        self._s3.put_object(
            ACL="private",  # https://docs.aws.amazon.com/AmazonS3/latest/dev/acl-overview.html#canned-acl
            Body=body,
            Bucket=S3_BUCKET_NAME,
            ContentType=mime_type,
            # https://aws.amazon.com/blogs/aws/amazon-s3-object-expiration/
            Expires=datetime.now() + timedelta(hours=1),
            Key=object_key,
        )

    @staticmethod
    def _clean_dir(dir_path, remove_dir=True):
        for filename in os.listdir(dir_path):
            os.unlink(os.path.join(dir_path, filename))
        if remove_dir:
            os.rmdir(dir_path)

    def process(self, arguments):
        self.results = []

        data = self.validate_parameter(arguments, "data", required=True, allowed_types=[DataCube])
        output_format = self.validate_parameter(arguments, "format", required=True, allowed_types=[str])
        output_format = output_format.lower()
        output_options = self.validate_parameter(arguments, "options", default={}, allowed_types=[dict])

        if output_format not in OUTPUT_FORMATS:
            raise ProcessParameterInvalid(
                "save_result",
                "format",
                f"Supported formats are: {', '.join(OUTPUT_FORMATS.keys())}.",
            )

        for option in output_options:
            if option not in ["datatype"]:
                raise ProcessParameterInvalid("save_result", "options", "Supported options are: 'datatype'.")

        if output_format == "json":
            serialized_data = serialize_data(data)
            json_string = json.dumps(serialized_data)
            self._put_file_to_s3("result.json", "application/json", body=json_string)
            self.results.append(
                {
                    "filename": "result.json",
                    "type": "application/json",
                }
            )
        else:
            if "x" not in data.dims or "y" not in data.dims:
                raise ProcessParameterInvalid(
                    "save_result",
                    "options",
                    f"Only spatial datacube can be saved as a raster image file.",
                )
                
            default_datatype = OUTPUT_FORMATS[output_format].default_datatype
            datatype_string = output_options.get("datatype", default_datatype).lower()
            datatype = self.GDAL_DATATYPES.get(datatype_string)

            if not datatype:
                raise ProcessParameterInvalid(
                    "save_result",
                    "options",
                    f"Unknown value for option 'datatype', allowed values are [{', '.join(self.GDAL_DATATYPES.keys())}].",
                )
            # https://stackoverflow.com/a/33950009
            tmp_job_dir = os.path.join("/tmp", self.job_id)
            try:
                os.mkdir(tmp_job_dir)
            except FileExistsError:
                save_resultEOTask._clean_dir(tmp_job_dir, remove_dir=False)

            bbox = data.attrs["bbox"]
            nx = len(data["x"])
            ny = len(data["y"])

            if "t" not in data.dims:
                data = data.expand_dims({"t": [datetime.now()]})
            n_timestamps = len(data["t"])

            if "band" not in data.dims:
                data = data.expand_dims({"band": ["generic_band"]}, axis=-1)
            n_bands = len(data["band"])

            xmin, ymin = bbox.lower_left
            xmax, ymax = bbox.upper_right
            xres = (xmax - xmin) / float(nx)
            yres = (ymax - ymin) / float(ny)
            geotransform = (xmin, xres, 0, ymax, 0, -yres)

            for ti in range(n_timestamps):
                timestamp = data["t"].to_index()[ti]
                t_str = timestamp.strftime("%Y-%m-%d_%H-%M-%S")
                filename = os.path.join(tmp_job_dir, f"result-{t_str}.{OUTPUT_FORMATS[output_format].ext}")

                # create the output GDAL dataset:
                # https://gdal.org/tutorials/raster_api_tut.html#techniques-for-creating-files
                dst_driver = gdal.GetDriverByName(output_format)
                if not dst_driver:
                    raise ProcessParameterInvalid("save_result", "format", "GDAL driver not supported.")
                metadata = dst_driver.GetMetadata()
                if metadata.get(gdal.DCAP_CREATE) == "YES":
                    dst_intermediate = dst_driver.Create(filename, xsize=nx, ysize=ny, bands=n_bands, eType=datatype)
                else:
                    # PNG and JPG are special in that Create() is not supported, but we can create a MEM
                    # GDAL dataset and later use CreateCopy() to copy it.
                    # https://gis.stackexchange.com/questions/132298/gdal-c-api-how-to-create-png-or-jpeg-from-scratch
                    dst_driver_mem = gdal.GetDriverByName("MEM")
                    dst_intermediate = dst_driver_mem.Create("", xsize=nx, ysize=ny, bands=n_bands, eType=datatype)

                if output_format == "gtiff":
                    # PNG and JPEG support this too, but the data is saved to a separate .aux.xml file
                    dst_intermediate.SetGeoTransform(geotransform)  # specify coords
                    srs = osr.SpatialReference()  # establish encoding
                    srs.ImportFromEPSG(4326)  # EPSG:4326 by default
                    dst_intermediate.SetProjection(srs.ExportToWkt())  # export coords to file

                for i in range(n_bands):
                    band_data = data[
                        {
                            "t": ti,
                            "band": i,
                        }
                    ].values
                    dst_intermediate.GetRasterBand(i + 1).WriteArray(band_data)  # write r-band to the raster

                # write to disk:
                if metadata.get(gdal.DCAP_CREATE) == "YES":
                    dst_intermediate.FlushCache()
                    dst_intermediate = None  # careful, this is needed, otherwise S3 mocking will fail in unit tests
                else:
                    # with PNG and JPG, we still need to copy from MEM to appropriate GDAL dataset:
                    dst_final = dst_driver.CreateCopy(filename, dst_intermediate, strict=0)
                    if not dst_final:
                        raise ProcessParameterInvalid(
                            "save_result",
                            "format",
                            f"Could not create data file in format [{output_format}] for [{n_bands}] bands and datatype [{datatype_string}].",
                        )
                    dst_final.FlushCache()
                    dst_final = None  # careful, this is needed, otherwise S3 mocking will fail in unit tests

                try:
                    self._put_file_to_s3(filename, OUTPUT_FORMATS[output_format].mime_type)
                except Exception as ex:
                    self.logger.exception("Saving file to S3 failed")
                    raise StorageFailure("Unable to store file(s).")

                self.results.append(
                    {
                        "filename": os.path.basename(filename),
                        "type": OUTPUT_FORMATS[output_format].mime_type,
                    }
                )

            save_resultEOTask._clean_dir(tmp_job_dir)

        # print(result.to_series())
        # API requests that we return True / False:
        return True
