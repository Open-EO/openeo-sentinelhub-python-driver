import pytest
import sys, os
import xarray as xr
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process
from process._common import ProcessParameterInvalid, ProcessArgumentRequired, DataCube, assert_equal, DimensionType


@pytest.fixture
def generate_data():
    def _construct(
        data=([[[[0.2, 0.8]]]], [[[[0.2, 0.8]]]]),
        attrs={"test_keep_attrs": 42},
        dims=("t", "y", "x", "band"),
        dim_types={
            "x": DimensionType.SPATIAL,
            "y": DimensionType.SPATIAL,
            "t": DimensionType.TEMPORAL,
            "band": DimensionType.BANDS,
        },
        as_list=False,
        as_dataarray=False,
    ):
        if as_list:
            return data

        if as_dataarray:
            return DataCube(data, dims=dims, attrs=attrs, dim_types=dim_types)

        data_list = []

        for d in data:
            xrdata = DataCube(d, dims=dims, attrs=attrs, dim_types=dim_types)
            data_list.append(xrdata)

        return data_list

    return _construct


@pytest.fixture
def execute_sum_process(generate_data):
    def wrapped(data_arguments={}, ignore_nodata=None):
        arguments = {}
        if data_arguments is not None:
            arguments["data"] = generate_data(**data_arguments)
        if ignore_nodata is not None:
            arguments["ignore_nodata"] = ignore_nodata

        return process.sum.sumEOTask(None, "", None, {}, "node1", {}).process(arguments)

    return wrapped


###################################
# tests:
###################################


@pytest.mark.parametrize(
    "data,ignore_nodata,expected_result", [([5, 1], True, 6), ([-2, 4, 2.5], True, 4.5), ([1, None], False, None)]
)
def test_examples(execute_sum_process, data, expected_result, ignore_nodata):
    """
    Test sum process with examples from https://open-eo.github.io/openeo-api/processreference/#sum
    """
    data_arguments = {"data": data, "as_list": True}
    result = execute_sum_process(data_arguments, ignore_nodata=ignore_nodata)
    assert result == expected_result


@pytest.mark.parametrize(
    "array1,array2,expected_data",
    [
        ([[[[0.2, 0.8]]]], [[[[0.2, 0.8]]]], [[[[0.4, 1.6]]]]),
    ],
)
def test_with_xarray(execute_sum_process, generate_data, array1, array2, expected_data):
    """
    Test sum process with xarray.DataArrays
    """
    expected_result = generate_data(data=[expected_data])[0]
    result = execute_sum_process({"data": (array1, array2)})
    assert_equal(result, expected_result)


@pytest.mark.parametrize(
    "array1,array2,ignore_nodata,expected_data",
    [
        ([[[[np.nan, np.nan]]]], [[[[0.2, np.nan]]]], True, [[[[0.2, 0.0]]]]),
        ([[[[np.nan, np.nan]]]], [[[[0.2, np.nan]]]], False, [[[[np.nan, np.nan]]]]),
    ],
)
def test_with_xarray_nulls(execute_sum_process, generate_data, array1, array2, expected_data, ignore_nodata):
    """
    Test sum process with xarray.DataArrays with null in data
    """
    expected_result = generate_data(data=[expected_data])[0]
    result = execute_sum_process({"data": (array1, array2)}, ignore_nodata=ignore_nodata)
    assert_equal(result, expected_result)


@pytest.mark.parametrize(
    "exception,data_arguments,ignore_nodata,exception_args",
    [
        (ProcessArgumentRequired, None, None, ("Process 'sum' requires argument 'data'.",)),
        (ProcessParameterInvalid, {}, 1, ("sum", "ignore_nodata", "Argument must be of types '[boolean]'.")),
    ],
)
def test_parameter_validation(execute_sum_process, exception, data_arguments, ignore_nodata, exception_args):
    """
    Test parameter validation
    """
    with pytest.raises(exception) as ex:
        result = execute_sum_process(data_arguments=data_arguments, ignore_nodata=ignore_nodata)
    assert ex.value.args == exception_args


@pytest.mark.parametrize(
    "data,reduce_by,expected_data,expected_dims",
    [
        ([[[[0.2, 0.8]]], [[[1.0, 2.0]]]], "t", [[[1.2, 2.8]]], ("y", "x", "band")),
    ],
)
def test_xarray_directly(execute_sum_process, generate_data, data, reduce_by, expected_data, expected_dims):
    """
    Test sum process by passing a DataArray to be reduced directly (instead of a list)
    """
    expected_result = generate_data(
        data=expected_data, dims=expected_dims, attrs={"reduce_by": reduce_by}, as_dataarray=True
    )
    result = execute_sum_process({"data": data, "attrs": {"reduce_by": reduce_by}, "as_dataarray": True})
    assert_equal(result, expected_result)


@pytest.mark.parametrize(
    "number1,number2,arr1,arr2,expected_data,num_first",
    [
        (
            0.2,
            -3,
            [[[[1.0, 2.0]]], [[[5.0, 6.0]]]],
            [[[[7.0, 8.0]]], [[[9.0, 10.0]]]],
            [[[[5.2, 7.2]]], [[[11.2, 13.20]]]],
            True,
        ),
        (
            0.2,
            -3,
            [[[[1.0, 2.0]]], [[[5.0, 6.0]]]],
            [[[[7.0, 8.0]]], [[[9.0, 10.0]]]],
            [[[[5.2, 7.2]]], [[[11.2, 13.20]]]],
            False,
        ),
    ],
)
def test_with_numbers(execute_sum_process, generate_data, number1, number2, arr1, arr2, expected_data, num_first):
    """
    Test sum process by a list of numbers and DataArrays
    """
    expected_result = generate_data(data=expected_data, as_dataarray=True)
    arr1 = generate_data(data=arr1, as_dataarray=True)
    arr2 = generate_data(data=arr2, as_dataarray=True)

    if num_first:
        data = [number1, arr1, number2, arr2]
    else:
        data = [arr1, number1, arr2, number2]

    result = execute_sum_process({"data": data, "as_list": True})
    assert_equal(result, expected_result)
