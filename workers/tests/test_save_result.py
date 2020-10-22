import datetime
import os
import sys

from botocore.stub import Stubber, ANY
from io import BufferedReader
import pandas as pd
import pytest
import xarray as xr

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessParameterInvalid, ProcessArgumentRequired


FIXTURES_FOLDER = os.path.join(os.path.dirname(__file__), "fixtures")

S3_BUCKET_NAME = "com.sinergise.openeo.results"
DATA_AWS_S3_ENDPOINT_URL = os.environ.get("DATA_AWS_S3_ENDPOINT_URL")
JOB_ID = "random_job_id"


@pytest.fixture
def save_resultEOTask():
    return process.save_result.save_resultEOTask(None, JOB_ID, None, {}, "node1", {})


@pytest.fixture
def create_result_object():
    class CustomEqualityObject(BufferedReader):
        def __init__(self, parent):
            self.content = parent.read()

        def __eq__(self, other):
            other_content = other.read()
            return self.content == other_content

    def _generate(file):
        filename = os.path.join(FIXTURES_FOLDER, file)
        obj = open(filename, "rb")
        return CustomEqualityObject(obj)

    return _generate


@pytest.fixture
def generate_data():
    def _construct(
        ymin=12.32271,
        ymax=12.33572,
        xmin=42.06347,
        xmax=42.07112,
        data=[[[[0.2]]]],
        dims=("t", "y", "x", "band"),
        coords={"band": ["ndvi"], "t": [datetime.datetime.now()]},
        attrs={},
    ):
        class BBox:
            @property
            def lower_left(self):
                return (ymin, xmin)

            @property
            def upper_right(self):
                return (ymax, xmax)

        fake_bbox = BBox()
        attrs = {"bbox": fake_bbox, **attrs}

        if "band" in coords:
            bands = coords["band"]
            aliases = [None] * len(bands)
            wavelengths = [None] * len(bands)
            coords["band"] = pd.MultiIndex.from_arrays(
                [bands, aliases, wavelengths], names=("_name", "_alias", "_wavelength")
            )

        xrdata = xr.DataArray(
            data,
            dims=dims,
            coords=coords,
            attrs=attrs,
        )

        return xrdata

    return _construct


@pytest.fixture
def execute_save_result_process(generate_data, save_resultEOTask):
    def wrapped(data_arguments={}, file_format="GTiff", options=None):
        arguments = {}
        if data_arguments is not None:
            arguments["data"] = generate_data(**data_arguments)
        if file_format is not None:
            arguments["format"] = file_format
        if options is not None:
            arguments["options"] = options

        return save_resultEOTask.process(arguments)

    return wrapped


@pytest.fixture
def s3_stub_generator(save_resultEOTask):
    client = save_resultEOTask._s3
    with Stubber(client) as stubber:

        def wrapper(stubber):
            def _set_params(body, bucket=S3_BUCKET_NAME, stubber=stubber):
                stubber.add_response(
                    "put_object",
                    expected_params={
                        "ACL": ANY,
                        "Body": body,
                        "Bucket": bucket,
                        "ContentType": ANY,
                        "Expires": ANY,
                        "Key": ANY,
                    },
                    service_response={},
                )
                return stubber

            return _set_params

        set_params = wrapper(stubber)

        yield set_params


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "parameters,expected_result_filename",
    [
        ({"file_format": "GTiff", "options": {"datatype": "float64"}}, "save_result_s3_file.tiff"),
        (
            {
                "file_format": "gtiff",
                "options": {"datatype": "byte"},
                "data_arguments": {
                    "data": [[[[0, 127, 255]]]],
                    "coords": {"band": ["r", "g", "b"], "t": [datetime.datetime.now()]},
                },
            },
            "save_result_s3_file_byte.tiff",
        ),
        (
            {
                "file_format": "png",
                "options": {"datatype": "byte"},
                "data_arguments": {
                    "data": [[[[0, 127, 255]]]],
                    "coords": {"band": ["r", "g", "b"], "t": [datetime.datetime.now()]},
                },
            },
            "save_result_s3_file.png",
        ),
        (
            {
                "file_format": "jpeg",
                "options": {"datatype": "byte"},
                "data_arguments": {
                    "data": [[[[255, 127, 0]]]],
                    "coords": {"band": ["r", "g", "b"], "t": [datetime.datetime.now()]},
                },
            },
            "save_result_s3_file.jpeg",
        ),
    ],
)
def test_correct(
    execute_save_result_process, s3_stub_generator, create_result_object, parameters, expected_result_filename
):
    """
    Test save_result process with correct parameters
    """
    s3_stub = s3_stub_generator(create_result_object(expected_result_filename))
    result = execute_save_result_process(**parameters)
    s3_stub.assert_no_pending_responses()
    assert result is True


@pytest.mark.parametrize(
    "missing_required_parameter,failure_reason",
    [
        ({"data_arguments": None}, "data"),
        ({"file_format": None}, "format"),
    ],
)
def test_required_params(execute_save_result_process, missing_required_parameter, failure_reason):
    """
    Test save_result process with missing required parameters
    """
    with pytest.raises(ProcessArgumentRequired) as ex:
        result = execute_save_result_process(**missing_required_parameter)

    assert ex.value.args[0] == "Process 'save_result' requires argument '{}'.".format(failure_reason)


@pytest.mark.parametrize(
    "invalid_parameter,failure_param,failure_reason",
    [
        ({"file_format": "xcf"}, "format", "Supported formats are: gtiff, png, jpeg."),
        (
            {"options": {"option_name": "option_value"}},
            "options",
            "Supported options are: 'datatype'.",
        ),
    ],
)
def test_invalid_params(execute_save_result_process, invalid_parameter, failure_param, failure_reason):
    """
    Test save_result process with invalid parameters
    """
    with pytest.raises(ProcessParameterInvalid) as ex:
        result = execute_save_result_process(**invalid_parameter)
    assert ex.value.args == ("save_result", failure_param, failure_reason)
