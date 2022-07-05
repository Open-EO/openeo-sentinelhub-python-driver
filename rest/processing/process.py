import warnings
import math
from datetime import datetime, date, timedelta, timezone

from sentinelhub import DataCollection, MimeType, BBox, Geometry, CRS
from sentinelhub.time_utils import parse_time
from pg_to_evalscript import convert_from_process_graph
from sentinelhub.geo_utils import bbox_to_dimensions
from isodate import parse_duration
from shapely.geometry import shape, mapping

from processing.openeo_process_errors import FormatUnsuitable
from processing.sentinel_hub import SentinelHub
from processing.const import (
    SampleType,
    default_sample_type_for_mimetype,
    supported_sample_types,
    sample_types_to_bytes,
    utm_tiling_grids,
)
from openeo_collections.collections import collections
from openeoerrors import (
    CollectionNotFound,
    Internal,
    ProcessParameterInvalid,
    ProcessGraphComplexity,
    TemporalExtentError,
)
from processing.partially_supported_processes import partially_supported_processes
from processing.utils import (
    convert_degree_resolution_to_meters,
    convert_to_epsg4326,
    construct_geojson,
    convert_geometry_crs,
    remove_partially_supported_processes_from_process_graph,
    is_geojson,
    validate_geojson,
    parse_geojson,
    get_spatial_info_from_partial_processes,
)


class Process:
    def __init__(self, process, width=None, height=None, access_token=None, user_defined_processes={}):
        self.DEFAULT_EPSG_CODE = 4326
        self.DEFAULT_RESOLUTION = (10, 10)
        self.MAXIMUM_SYNC_FILESIZE_BYTES = 5000000
        partially_supported_processes_as_udp = {
            partially_supported_process.process_id: {} for partially_supported_process in partially_supported_processes
        }
        partially_supported_processes_as_udp.update(user_defined_processes)
        self.user_defined_processes = partially_supported_processes_as_udp
        self.sentinel_hub = SentinelHub(access_token=access_token)

        self.process_graph = process["process_graph"]
        (
            self.pisp_geometry,
            self.pisp_crs,
            self.pisp_resolution,
            self.pisp_resampling_method,
        ) = get_spatial_info_from_partial_processes(partially_supported_processes, self.process_graph)
        self.bbox, self.epsg_code, self.geometry = self.get_bounds()
        self.collection = self.get_collection()
        self.from_date, self.to_date = self.get_temporal_extent()
        self.mimetype = self.get_mimetype()
        self.width = width or self.get_dimensions()[0]
        self.height = height or self.get_dimensions()[1]
        self.tiling_grid_id, self.tiling_grid_resolution = self.get_appropriate_tiling_grid_and_resolution()
        self.sample_type = self.get_sample_type()
        self.evalscript = self.get_evalscript()

    def convert_to_sh_bbox(self):
        return BBox(self.bbox, CRS(self.epsg_code))

    def get_evalscript(self):
        process_graph = remove_partially_supported_processes_from_process_graph(
            self.process_graph, partially_supported_processes
        )
        results = convert_from_process_graph(
            process_graph,
            sample_type=self.sample_type.value,
            user_defined_processes=self.user_defined_processes,
            encode_result=False,
        )
        evalscript = results[0]["evalscript"]

        if self.get_input_bands() is None:
            load_collection_node = self.get_node_by_process_id("load_collection")
            collection = collections.get_collection(load_collection_node["arguments"]["id"])
            all_bands = collection["cube:dimensions"]["bands"]["values"]
            evalscript.set_input_bands(all_bands)

        return evalscript

    def _create_custom_datacollection(self, collection_type, collection_info, subtype):
        service_url = next(
            provider["url"] for provider in collection_info["providers"] if "processor" in provider["roles"]
        )
        byoc_collection_id = collection_type.replace(f"{subtype}-", "")
        return DataCollection.define_byoc(byoc_collection_id, service_url=service_url)

    def id_to_data_collection(self, collection_id):
        collection_info = collections.get_collection(collection_id)

        if not collection_info:
            raise CollectionNotFound()

        collection_type = collection_info["datasource_type"]

        if collection_type == "byoc-ID":
            load_collection_node = self.get_node_by_process_id("load_collection")
            featureflags = load_collection_node["arguments"].get("featureflags", {})
            byoc_collection_id = featureflags.get("byoc_collection_id")

            if not byoc_collection_id:
                raise Internal(
                    f"Collection {collection_id} requires 'byoc_collection_id' parameter to be set in 'featureflags' argument of 'load_collection'."
                )
            return self._create_custom_datacollection(byoc_collection_id, collection_info, "byoc")

        if collection_type.startswith("byoc"):
            return self._create_custom_datacollection(collection_type, collection_info, "byoc")

        if collection_type.startswith("batch"):
            return self._create_custom_datacollection(collection_type, collection_info, "batch")

        for data_collection in DataCollection:
            if data_collection.value.api_id == collection_type:
                return data_collection

        raise Internal(f"Collection {collection_id} could not be mapped to a Sentinel Hub collection type.")

    def get_node_by_process_id(self, process_id):
        for node in self.process_graph.values():
            if node["process_id"] == process_id:
                return node

    def get_collection(self):
        load_collection_node = self.get_node_by_process_id("load_collection")
        return self.id_to_data_collection(load_collection_node["arguments"]["id"])

    def get_bounds_from_load_collection(self):
        """
        Returns bbox, EPSG code, geometry
        """
        load_collection_node = self.get_node_by_process_id("load_collection")
        spatial_extent = load_collection_node["arguments"]["spatial_extent"]

        if spatial_extent is None:
            collection = collections.get_collection(load_collection_node["arguments"]["id"])
            bbox = collection["extent"]["spatial"]["bbox"][0]
            return tuple(bbox), self.DEFAULT_EPSG_CODE, None
        elif is_geojson(spatial_extent):
            if validate_geojson(spatial_extent):
                geojson = parse_geojson(spatial_extent)
                sh_py_geometry = Geometry.from_geojson(geojson)
                return (
                    (
                        *sh_py_geometry.bbox.lower_left,
                        *sh_py_geometry.bbox.upper_right,
                    ),
                    self.DEFAULT_EPSG_CODE,
                    spatial_extent,
                )
        else:
            epsg_code = spatial_extent.get("crs", self.DEFAULT_EPSG_CODE)
            east = spatial_extent["east"]
            west = spatial_extent["west"]
            north = spatial_extent["north"]
            south = spatial_extent["south"]
            return (west, south, east, north), epsg_code, None

    def get_bounds(self):
        bbox, epsg_code, geometry = self.get_bounds_from_load_collection()
        partial_processes_geometry = self.pisp_geometry
        partial_processes_crs = self.pisp_crs

        if partial_processes_geometry is None:
            return bbox, epsg_code, geometry

        if geometry:
            geometry = shape(geometry)
        elif bbox:
            west, south, east, north = bbox
            if epsg_code != 4326:
                west, south = convert_to_epsg4326(epsg_code, west, south)
                east, north = convert_to_epsg4326(epsg_code, east, north)
            geometry = shape(construct_geojson(west, south, east, north))

        final_geometry = partial_processes_geometry.intersection(geometry)

        if partial_processes_crs is not None and partial_processes_crs != 4326:
            final_geometry = convert_geometry_crs(final_geometry, partial_processes_crs)

        return final_geometry.bounds, partial_processes_crs, mapping(final_geometry)

    def get_collection_temporal_step(self):
        load_collection_node = self.get_node_by_process_id("load_collection")
        collection = collections.get_collection(load_collection_node["arguments"]["id"])
        if not collection:
            return None
        return collection["cube:dimensions"]["t"].get("step")

    def get_temporal_interval(self, in_days=False):
        step = self.get_collection_temporal_step()

        if step is None:
            return None

        temporal_interval = parse_duration(step)

        if in_days:
            n_seconds_per_day = 86400
            return temporal_interval.total_seconds() / n_seconds_per_day
        return temporal_interval.total_seconds()

    def get_maximum_temporal_extent_for_collection(self):
        load_collection_node = self.get_node_by_process_id("load_collection")
        openeo_collection = collections.get_collection(load_collection_node["arguments"]["id"])
        from_time, to_time = openeo_collection.get("extent").get("temporal")["interval"][0]

        if from_time is not None:
            from_time = parse_time(from_time)
        else:
            current_date = datetime.now()
            from_time = current_date.replace(hour=0, minute=0, second=0, microsecond=0)

        if to_time is not None:
            to_time = parse_time(to_time)
        else:
            current_date = datetime.now()
            to_time = current_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return from_time, to_time

    def get_temporal_extent(self):
        """
        Returns from_time, to_time
        """
        load_collection_node = self.get_node_by_process_id("load_collection")
        temporal_extent = load_collection_node["arguments"].get("temporal_extent")
        if temporal_extent is None:
            temporal_extent = self.get_maximum_temporal_extent_for_collection()

        interval_start, interval_end = temporal_extent
        if interval_start is None:
            from_time, _ = self.get_maximum_temporal_extent_for_collection()
        else:
            from_time = parse_time(interval_start)

        if interval_end is None:
            _, to_time = self.get_maximum_temporal_extent_for_collection()
        else:
            to_time = parse_time(interval_end)

        # type(d) is date is used because Datetime is a subclass of Date and isinstance(d, Date) is always True
        if type(from_time) is date:
            from_time = datetime(from_time.year, from_time.month, from_time.day)
        if type(to_time) is date:
            to_time = datetime(to_time.year, to_time.month, to_time.day)

        if from_time.tzinfo is None:
            from_time = from_time.replace(tzinfo=timezone.utc)
        if to_time.tzinfo is None:
            to_time = to_time.replace(tzinfo=timezone.utc)

        to_time = to_time - timedelta(microseconds=1)  # End of the interval is not inclusive
        if to_time < from_time:
            raise TemporalExtentError()

        return from_time, to_time

    def get_input_bands(self):
        load_collection_node = self.get_node_by_process_id("load_collection")
        return load_collection_node["arguments"].get("bands")

    def format_to_mimetype(self, output_format):
        OUTPUT_FORMATS = {
            "gtiff": MimeType.TIFF,
            "png": MimeType.PNG,
            "jpeg": MimeType.JPG,
        }
        output_format = output_format.lower()
        if output_format in OUTPUT_FORMATS:
            return OUTPUT_FORMATS[output_format]
        else:
            raise FormatUnsuitable()

    def get_mimetype(self):
        save_result_node = self.get_node_by_process_id("save_result")
        return self.format_to_mimetype(save_result_node["arguments"]["format"])

    def get_sample_type(self):
        save_result_node = self.get_node_by_process_id("save_result")

        if save_result_node["arguments"].get("options", {}).get("datatype"):
            datatype = save_result_node["arguments"]["options"]["datatype"]
            sample_type = SampleType.from_gdal_datatype(datatype)
            if not sample_type:
                raise ProcessParameterInvalid("options", "save_result", f"{datatype} is not a supported 'datatype'.")
            if sample_type not in supported_sample_types[self.mimetype]:
                output_format = save_result_node["arguments"]["format"]
                raise ProcessParameterInvalid(
                    "options", "save_result", f"{datatype} is not a valid 'datatype' for format {output_format}."
                )
            return sample_type

        return default_sample_type_for_mimetype.get(self.mimetype, SampleType.UINT8)

    def get_dimensions(self):
        """
        Returns the expected dimensions of only the AOI based on the resolution.
        This is not accurate for Batch API, as it processes more area than requested.
        """
        spatial_extent = self.bbox
        bbox = self.convert_to_sh_bbox()
        if self.pisp_resolution is not None:
            resolution = tuple(self.pisp_resolution)
        else:
            resolution = self.get_highest_resolution()
        width, height = bbox_to_dimensions(bbox, resolution)
        return width, height

    def get_highest_resolution(self):
        load_collection_node = self.get_node_by_process_id("load_collection")
        collection = collections.get_collection(load_collection_node["arguments"]["id"])
        selected_bands = self.get_input_bands()
        summaries = collection.get("summaries", {})

        if selected_bands is None:
            selected_bands = collection["cube:dimensions"]["bands"]["values"]

        bands_summaries = None
        for key in ["eo:bands", "raster:bands"]:
            bands_summaries = summaries.get(key, bands_summaries)

        if bands_summaries is None:
            return self.DEFAULT_RESOLUTION

        list_of_resolutions = [
            self.get_band_resolution(band_summary)
            for band_summary in bands_summaries
            if band_summary["name"] in selected_bands
        ]
        highest_x_resolution = min(list_of_resolutions, key=lambda x: x[0])[0]
        highest_y_resolution = min(list_of_resolutions, key=lambda x: x[1])[1]
        return (highest_x_resolution, highest_y_resolution)

    def get_band_resolution(self, band_summary):
        band_resolution_tuple = band_summary.get("openeo:gsd", {})
        resolution_unit = band_resolution_tuple.get("unit", "m")
        resolution = band_resolution_tuple.get("value", self.DEFAULT_RESOLUTION)

        # Some bands can have multiple resolutions, like sentinel-1-gdr where we have high and medium https://docs.sentinel-hub.com/api/latest/data/sentinel-1-grd/#resolution-pixel-spacing
        # By default we will use highest resolution
        if isinstance(resolution[0], list):
            # Get coord list where x,y resolution is the highest.
            # We can assume that x and y are not always equal, so we sum x and y and get the list with the lowest sum
            highest_resolution = min(resolution, key=lambda coord: coord[0] + coord[1])
            resolution = highest_resolution

        if resolution_unit == "°":
            # assumes that wgs84 is used
            resolution = convert_degree_resolution_to_meters(resolution)

        return resolution

    def get_appropriate_tiling_grid_and_resolution(self):
        global utm_tiling_grids
        requested_resolution = min(self.get_highest_resolution())
        utm_tiling_grids = sorted(
            utm_tiling_grids, key=lambda tg: tg["properties"]["tileWidth"]
        )  # We prefer grids with smaller tiles
        best_tiling_grid_id = None
        best_tiling_grid_resolution = math.inf

        for tiling_grid in utm_tiling_grids:
            resolutions = tiling_grid["properties"]["resolutions"]

            for resolution in resolutions:
                if resolution <= requested_resolution and abs(resolution - requested_resolution) < abs(
                    best_tiling_grid_resolution - requested_resolution
                ):
                    best_tiling_grid_id = tiling_grid["id"]
                    best_tiling_grid_resolution = resolution

        if best_tiling_grid_id is None and best_tiling_grid_resolution is None:
            return utm_tiling_grids[0]["id"], min(utm_tiling_grids[0]["properties"]["resolutions"])

        return best_tiling_grid_id, best_tiling_grid_resolution

    def estimate_file_size(self, n_pixels=None):
        if n_pixels is None:
            n_pixels = self.width * self.height

        n_bytes = sample_types_to_bytes.get(self.sample_type)
        output_dimensions = self.evalscript.determine_output_dimensions()
        n_original_temporal_dimensions = 0
        n_output_bands = 1

        for output_dimension in output_dimensions:
            if output_dimension.get("original_temporal"):
                n_original_temporal_dimensions += 1
            else:
                n_output_bands *= output_dimension["size"]

        if n_original_temporal_dimensions > 0:
            temporal_interval = self.get_temporal_interval()

            if temporal_interval is None:
                n_seconds_per_day = 86400
                default_temporal_interval = 3
                temporal_interval = default_temporal_interval * n_seconds_per_day

            date_diff = (self.to_date - self.from_date).total_seconds()
            n_dates = math.ceil(date_diff / temporal_interval) + 1
            n_output_bands *= n_dates * n_original_temporal_dimensions

        if self.mimetype == MimeType.PNG:
            n_output_bands = min(n_output_bands, 4)
        elif self.mimetype == MimeType.JPG:
            n_output_bands = min(n_output_bands, 3)

        return n_pixels * n_bytes * n_output_bands

    def execute_sync(self):
        estimated_file_size = self.estimate_file_size()
        if estimated_file_size > self.MAXIMUM_SYNC_FILESIZE_BYTES:
            raise ProcessGraphComplexity(
                f"estimated size of generated output of {estimated_file_size} bytes exceeds maximum supported size of {self.MAXIMUM_SYNC_FILESIZE_BYTES} bytes."
            )

        return self.sentinel_hub.create_processing_request(
            bbox=self.bbox,
            epsg_code=self.epsg_code,
            geometry=self.geometry,
            collection=self.collection,
            evalscript=self.evalscript.write(),
            from_date=self.from_date,
            to_date=self.to_date,
            width=self.width,
            height=self.height,
            mimetype=self.mimetype,
            resampling_method=self.pisp_resampling_method,
        )

    def create_batch_job(self):
        return self.sentinel_hub.create_batch_job(
            bbox=self.bbox,
            epsg_code=self.epsg_code,
            geometry=self.geometry,
            collection=self.collection,
            evalscript=self.evalscript.write(),
            from_date=self.from_date,
            to_date=self.to_date,
            tiling_grid_id=self.tiling_grid_id,
            tiling_grid_resolution=self.tiling_grid_resolution,
            mimetype=self.mimetype,
            resampling_method=self.pisp_resampling_method,
        )
