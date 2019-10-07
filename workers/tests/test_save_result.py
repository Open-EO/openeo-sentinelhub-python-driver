import pytest
import sys, os
import xarray as xr
import datetime
from botocore.stub import Stubber,ANY
from io import BufferedReader

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessArgumentInvalid, ProcessArgumentRequired
FIXTURES_FOLDER = os.path.join(os.path.dirname(__file__), 'fixtures')

S3_BUCKET_NAME = 'com.sinergise.openeo.results'
DATA_AWS_S3_ENDPOINT_URL = os.environ.get('DATA_AWS_S3_ENDPOINT_URL')
JOB_ID = "random_job_id"

@pytest.fixture
def save_resultEOTask():
    return process.save_result.save_resultEOTask(None, JOB_ID , None)

@pytest.fixture
def create_custom_object():
    class CustomEqualityObject(BufferedReader):
        def __init__(self, parent):
            self.content = parent.read()

        def __eq__(self,other):
            other_content = other.read()
            return self.content == other_content

    def _generate(obj):
        return CustomEqualityObject(obj)

    return _generate

@pytest.fixture
def gtiff_object(create_custom_object):
    filename = os.path.join(FIXTURES_FOLDER, 'gtiff_object.tiff')
    body = open(filename, 'rb')

    return create_custom_object(body)

@pytest.fixture
def generate_data():
    def _construct(
            ymin = 12.32271,
            ymax = 12.33572,
            xmin = 42.06347,
            xmax = 42.07112,
            data = [[[[0.2]]]],
            dims = ('t','y', 'x', 'band'),
            coords = {'band': ["ndvi"],'t': [datetime.datetime.now()]},
            band_aliases = { "nir": "B08", "red": "B04"},
            attrs = {}
        ):
        class BBox:
            def get_lower_left(self):
                return (ymin,xmin)

            def get_upper_right(self):
                return (ymax,xmax)

        fake_bbox = BBox()
        attrs = {"band_aliases": band_aliases, "bbox": fake_bbox, **attrs}

        xrdata = xr.DataArray(
            data,
            dims=dims,
            coords=coords,
            attrs=attrs,
        )

        return xrdata
    return _construct

@pytest.fixture
def arguments_factory(generate_data):
    def wrapped(data_arguments=None, format_type=None, options=None):
        arguments = {}
        if data_arguments is not None: arguments["data"] = generate_data(**data_arguments)
        if format_type is not None: arguments["format"] = format_type
        if options is not None: arguments["options"] = options

        return arguments

    return wrapped

@pytest.fixture
def execute_save_result_process(arguments_factory, save_resultEOTask):
    def wrapped(set_arguments={"data_arguments": {}, "format_type": "Gtiff"}):
        arguments = arguments_factory(**set_arguments)
        return save_resultEOTask.process(arguments)
    return wrapped

@pytest.fixture
def s3_stub_generator(save_resultEOTask):
    client = save_resultEOTask._s3
    with Stubber(client) as stubber:
        def wrapper(stubber):
            def _set_params(body, bucket=S3_BUCKET_NAME, stubber=stubber):
                stubber.add_response(
                    'put_object',
                    expected_params = {
                        'ACL': ANY,
                        'Body': body,
                        'Bucket': bucket,
                        'ContentType': ANY,
                        'Expires': ANY,
                        'Key': ANY
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

def test_correct(execute_save_result_process, s3_stub_generator, gtiff_object):
    """
        Test save_result process with correct parameters
    """
    s3_stub = s3_stub_generator(gtiff_object)
    result = execute_save_result_process()
    s3_stub.assert_no_pending_responses()

    assert isinstance(result,bool) and result == True

@pytest.mark.parametrize(
    'missing_required_parameter,failure_reason', [
    ({"format_type": "Gtiff"}, "data"),
    ({"data_arguments": {}}, "format"),
])
def test_required_params(execute_save_result_process, missing_required_parameter, failure_reason):
    with pytest.raises(ProcessArgumentRequired) as ex:
        result = execute_save_result_process(set_arguments=missing_required_parameter)

    assert ex.value.args[0] == "Process 'save_result' requires argument '{}'.".format(failure_reason)


@pytest.mark.parametrize(
    'invalid_parameter,failure_reason', [
    ({"data_arguments": {}, "format_type": "png"}, ("format","supported formats are: 'GTiff'")),
    ({"data_arguments": {}, "format_type": "Gtiff", "options": {"option_name": "option_value"}}, ("options","output options are currently not supported"))
])
def test_invalid_params(execute_save_result_process, invalid_parameter, failure_reason):
    with pytest.raises(ProcessArgumentInvalid) as ex:
        result = execute_save_result_process(set_arguments=invalid_parameter)

    assert ex.value.args[0] == "The argument '{}' in process 'save_result' is invalid: {}.".format(*failure_reason)