import os
import logging
import time
import traceback

from functools import wraps
from flask import request, g
from http.client import HTTPConnection
from logging import getLogger, DEBUG

class ContextFilter(logging.Filter):
    def filter(self, record):
        record.req_id = request.req_id
        return True

LOGGING_LEVEL = os.environ.get("LOGGING_LEVEL")
logger = logging.getLogger("APILogger")
logger.setLevel(logging._nameToLevel[LOGGING_LEVEL])
hndlr = logging.StreamHandler()
fmt = logging.Formatter(f"%(levelname)s:%(name)s: - - [%(asctime)s (UTC)] - Request ID: %(req_id)s %(message)s")
fmt.converter = time.gmtime
hndlr.setFormatter(fmt)
logger.addHandler(hndlr)
fltr = ContextFilter()
logger.addFilter(fltr)
logger.propagate = False


if logging._nameToLevel[LOGGING_LEVEL] == DEBUG:
    HTTPConnection.debuglevel = 1
requests_log = getLogger("requests.packages.urllib3")
requests_log.setLevel(DEBUG)
requests_log.propagate = True


def with_logging(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        msg = f"\"{request.method} {request.path}\" [{g.get('user') or 'Unathenticated'}]. \nRequest args: {request.args.to_dict(flat=False)}. Request payload: {request.get_json(silent=True)}"
        logger.debug(msg)

        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.info(msg=f"Error: {str(e)}")
            logger.info(traceback.format_exc())
            raise e

    return decorated_function
