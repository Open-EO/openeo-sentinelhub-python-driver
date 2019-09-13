from os.path import dirname, basename, isfile, join
import glob
import importlib

from ._common import ExecFailedError, InvalidInputError


""" Find all.py files in this directory that do not start with underscore, and
    make them a part of this package.
"""
modules_files = glob.glob(join(dirname(__file__), "*.py"))
modules = [ basename(f)[:-3] for f in modules_files if isfile(f) and not basename(f).startswith('_')]
for f in modules:
    importlib.import_module(".{process_id}".format(process_id=f), package=__package__)
