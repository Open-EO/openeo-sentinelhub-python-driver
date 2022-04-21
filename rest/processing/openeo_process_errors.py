class OpenEOProcessError(Exception):
    error_code = None
    http_code = 400
    message = None


class FormatUnsuitable(OpenEOProcessError):
    # https://github.com/Open-EO/openeo-processes/blob/d0ce91fcd347360b907ea2d9589d7564a2c1e1e3/save_result.json#L49-L52
    error_code = "FormatUnsuitable"
    http_code = 400
    message = "Data can't be transformed into the requested output format."
