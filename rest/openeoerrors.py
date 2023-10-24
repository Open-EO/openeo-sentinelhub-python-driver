# These exceptions should translate to the list of OpenEO error codes:
# https://openeo.org/documentation/1.0/developers/api/errors.html


class OpenEOError(Exception):
    record_id = None


class AuthenticationRequired(OpenEOError):
    error_code = "AuthenticationRequired"
    http_code = 401
    message = "Unauthorized."


class AuthenticationSchemeInvalid(OpenEOError):
    error_code = "AuthenticationSchemeInvalid"
    http_code = 403
    message = "Authentication method not supported."


class TokenInvalid(OpenEOError):
    error_code = "TokenInvalid"
    http_code = 403
    message = "Authorization token has expired or is invalid. Please authenticate again."


class CredentialsInvalid(OpenEOError):
    error_code = "CredentialsInvalid"
    http_code = 403
    message = "Credentials are not correct."


class CollectionNotFound(OpenEOError):
    error_code = "CollectionNotFound"
    http_code = 404
    message = "Collection not found."


class JobNotFinished(OpenEOError):
    error_code = "JobNotFinished"
    http_code = 400
    message = "Job has not finished computing the results yet. Please try again later."


class JobNotFound(OpenEOError):
    error_code = "JobNotFound"
    http_code = 404
    message = "The job does not exist."


class JobLocked(OpenEOError):
    error_code = "JobLocked"
    http_code = 400
    message = "Job is locked due to a queued or running batch computation."


class ProcessUnsupported(OpenEOError):
    def __init__(self, process_id):
        self.message = f"Process with identifier '{process_id}' is not available in namespace 'Sentinel Hub'."  # Not sure what the namespace is supposed to be

    error_code = "ProcessUnsupported"
    http_code = 400


class Internal(OpenEOError):
    def __init__(self, message):
        self.message = f"Server error: {message}"

    error_code = "Internal"
    http_code = 500


class ServiceNotFound(OpenEOError):
    def __init__(self, service_id):
        self.message = f"Service '{service_id}' does not exist."

    error_code = "ServiceNotFound"
    http_code = 404


class ProcessGraphComplexity(OpenEOError):
    def __init__(self, reason):
        self.message = (
            f"The process is too complex for synchronous processing. Please use a batch job instead. {reason}"
        )

    error_code = "ProcessGraphComplexity"
    http_code = 400


class ProcessParameterInvalid(OpenEOError):
    def __init__(self, parameter, process, reason):
        self.message = f"The value passed for parameter '{parameter}' in process '{process}' is invalid: {reason}"

    error_code = "ProcessParameterInvalid"
    http_code = 400


class Timeout(OpenEOError):
    error_code = "Timeout"
    http_code = 408
    message = "Request timed out."


class BillingPlanInvalid(OpenEOError):
    error_code = "BillingPlanInvalid"
    http_code = 400
    message = "The billing plan is invalid."


class SHOpenEOError(Exception):
    # Class for exceptions that are not listed in https://openeo.org/documentation/0.4/developers/api/errors.html#openeo-error-codes
    record_id = None


class ProcessGraphNotFound(SHOpenEOError):
    error_code = "ProcessGraphNotFound"
    http_code = 404
    message = "Process graph does not exist."


class UnsupportedGeometry(SHOpenEOError):
    error_code = "UnsupportedGeometry"
    http_code = 400
    message = "Unsupported geometry found, only Polygon or MultiPolygon geometries are supported"


class TemporalExtentError(SHOpenEOError):
    error_code = "TemporalExtentError"
    http_code = 400
    message = "Invalid temporal_extent"


class BadRequest(SHOpenEOError):
    def __init__(self, message):
        self.message = f"Invalid request: {message}"

    error_code = "BadRequest"
    http_code = 400


class PartiallySupportedProcessInvalid(SHOpenEOError):
    def __init__(self, process_id, reason):
        self.message = f"Partially supported process '{process_id}' invalid: {reason}"

    error_code = "PartiallySupportedProcessInvalid"
    http_code = 400


class ImageDimensionInvalid(SHOpenEOError):
    def __init__(self, width, height) -> None:
        self.message = f"Requested image of {width}x{height} is below the limit of 1x1"

    error_code = "ImageDimensionInvalid"
    http_code = 400


class InsufficientCredits(SHOpenEOError):
    error_code = "InsufficientCredits"
    http_code = 402
    message = "You do not have sufficient credits to perform this request. Please visit https://portal.terrascope.be/pages/pricing to find more information on how to buy additional credits."
