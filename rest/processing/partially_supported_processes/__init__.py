import os
import glob

from .filter_bbox import FilterBBox
from .filter_spatial import FilterSpatial
from .resample_spatial import ResampleSpatial

partially_supported_processes = [FilterBBox, FilterSpatial, ResampleSpatial]
