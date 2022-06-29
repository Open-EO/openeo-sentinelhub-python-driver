import os
import glob

from .filter_bbox import FilterBBox

partially_supported_processes = glob.glob(f"{os.path.dirname(os.path.abspath(__file__))}/[!_]*.py")
partially_supported_processes = [
    os.path.splitext(os.path.basename(partially_supported_process))[0]
    for partially_supported_process in partially_supported_processes
]
