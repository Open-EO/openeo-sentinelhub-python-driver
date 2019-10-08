from ._common import ProcessEOTask, ProcessArgumentInvalid, ProcessArgumentRequired
import process

class reduceEOTask(ProcessEOTask):
    def process(self, arguments):
        try:
            data = arguments["data"]
        except:
            raise ProcessArgumentRequired("Process 'reduce' requires argument 'data'.")

        try:
            dimension = arguments["dimension"]

            if dimension not in data.dims:
                raise ProcessArgumentInvalid("The argument 'dimension' in process 'reduce' is invalid: Dimension '{}' does not exist in data.".format(dimension))
        except:
            raise ProcessArgumentRequired("Process 'reduce' requires argument 'dimension'.")

        reducer = arguments.get("reducer")
        target_dimension = arguments.get("target_dimension")
        binary = arguments.get("binary", False)

        if reducer is None:
            if data[dimension].size > 1:
                raise ProcessArgumentInvalid("The argument 'dimension' in process 'reduce' is invalid: Dimension '{}' has more than one value, but reducer is not specified.".format(dimension))
            result = data.squeeze(dimension, drop=True)
        else:
            pass

        return result
