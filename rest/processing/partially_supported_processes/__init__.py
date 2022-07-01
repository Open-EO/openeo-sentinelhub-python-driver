import os
import glob

from .filter_bbox import FilterBBox
from .filter_spatial import FilterSpatial

partially_supported_processes = [FilterBBox, FilterSpatial]
