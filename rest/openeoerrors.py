# These exceptions should translate to the list of OpenEO error codes:
#   https://api.openeo.org/errors.json


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
