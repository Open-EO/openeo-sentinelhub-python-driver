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
    message = "Invalid authentication scheme (e.g. Bearer)."


class TokenInvalid(OpenEOError):
    error_code = "TokenInvalid"
    http_code = 403
    message = "Authorization token has expired or is invalid. Please authenticate again."


class CredentialsInvalid(OpenEOError):
    error_code = "CredentialsInvalid"
    http_code = 403
    message = "Credentials are not correct."


class ProcessUnsupported(OpenEOError):
    def __init__(self, unsupported_process):
        self.message = f"Process with identifier '{process}' is not available in namespace 'Sentinel Hub'."  # Not sure what the namespace is supposed to be

    error_code = "ProcessUnsupported"
    http_code = 400


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
