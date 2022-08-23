class OpenEOProcessError(Exception):
    error_code = None
    http_code = 400
    message = None


class FormatUnsuitable(OpenEOProcessError):
    # https://github.com/Open-EO/openeo-processes/blob/d0ce91fcd347360b907ea2d9589d7564a2c1e1e3/save_result.json#L49-L52
    error_code = "FormatUnsuitable"
    http_code = 400
    message = "Data can't be transformed into the requested output format."


class NoDataAvailable(OpenEOProcessError):
    # https://github.com/Open-EO/openeo-processes/blob/40b8b458d4633cabceca7c261000dc6d081cbb7f/load_collection.json#L225
    def __init__(self, explanation):
        self.message = f"There is no data available for the given extents: {explanation}"

    error_code = "NoDataAvailable"
    http_code = 400
