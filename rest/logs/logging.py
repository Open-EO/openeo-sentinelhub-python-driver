import os
import logging
import datetime
import traceback

from functools import wraps
from flask import request, g
from http.client import HTTPConnection
from logging import getLogger, log, DEBUG, INFO
from werkzeug.exceptions import HTTPException
from processing.openeo_process_errors import OpenEOProcessError
from openeoerrors import OpenEOError, SHOpenEOError, Internal

LOGGING_LEVEL = os.environ.get("LOGGING_LEVEL")
logger = logging.getLogger("APILogger")
logger.setLevel(logging._nameToLevel[LOGGING_LEVEL])

if logging._nameToLevel[LOGGING_LEVEL] == DEBUG:
    HTTPConnection.debuglevel = 1
requests_log = getLogger("requests.packages.urllib3")
requests_log.setLevel(DEBUG)
requests_log.propagate = True


def with_logging(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        msg = f" - - [{datetime.datetime.utcnow()} (UTC)] \"{request.method} {request.path}\" [{g.get('user') or 'Unathenticated'}]. \nReq ID: {request.req_id} Request args: {request.args}. Request payload: {request.get_json(silent=True)}"
        logger.debug(msg)

        try:
            return func(*args, **kwargs)
        except Exception as e:
            # pass through HTTP errors
            log(INFO, f"Error: {str(e)}")
            if isinstance(e, HTTPException):
                return e

            # now you're handling non-HTTP exceptions only
            log(INFO, traceback.format_exc())

            if not issubclass(type(e), (OpenEOError, OpenEOProcessError, SHOpenEOError)):
                e = Internal(str(e))

            raise e

    return decorated_function
