import warnings
import math
from datetime import datetime, date, timedelta, timezone

from sentinelhub import DataCollection, MimeType, BBox, Geometry, CRS, ServiceUrl
from sentinelhub.time_utils import parse_time
from pg_to_evalscript import convert_from_process_graph
from sentinelhub.geo_utils import bbox_to_dimensions
from isodate import parse_duration
from shapely.geometry import shape, mapping

from processing.openeo_process_errors import FormatUnsuitable, NoDataAvailable
from processing.sentinel_hub import SentinelHub
from processing.const import (
    SampleType,
    default_sample_type_for_mimetype,
    supported_sample_types,
    sample_types_to_bytes,
    ProcessingRequestTypes,
)
from openeo_collections.collections import collections
from openeoerrors import (
    CollectionNotFound,
    DataFusionNotPossibleDifferentSHDeployments,
    Internal,
    ProcessParameterInvalid,
    ProcessGraphComplexity,
    TemporalExtentError,
    BadRequest,
    ImageDimensionInvalid,
)
from processing.partially_supported_processes import partially_supported_processes
from processing.utils import (
    convert_degree_resolution_to_meters,
    convert_to_epsg4326,
    construct_geojson,
    convert_geometry_crs,
    convert_bbox_crs,
    get_all_load_collection_nodes,
    remove_partially_supported_processes_from_process_graph,
    is_geojson,
    validate_geojson,
    parse_geojson,
    get_spatial_info_from_partial_processes,
    get_node_by_process_id,
)
from authentication.user import User


HLS_COLLECTION = DataCollection.define(
    "hls",
    api_id="hls",
    service_url=ServiceUrl.USWEST,
    collection_type="hls",
)


class Process:
    def __init__(self, process, width=None, height=None, user=User(), user_defined_processes={}, request_type=None):
        self.DEFAULT_EPSG_CODE = 4326
        self.DEFAULT_RESOLUTION = (10, 10)
        self.MAXIMUM_SYNC_FILESIZE_BYTES = 5000000
        partially_supported_processes_as_udp = {
            partially_supported_process.process_id: {} for partially_supported_process in partially_supported_processes
        }
        partially_supported_processes_as_udp.update(user_defined_processes)
        self.user_defined_processes = partially_supported_processes_as_udp
        self.request_type = request_type
        self.process_graph = process["process_graph"]
        (
            self.pisp_geometry,
            self.pisp_crs,
            self.pisp_resolution,
            self.pisp_resampling_method,
        ) = get_spatial_info_from_partial_processes(partially_supported_processes, self.process_graph)
        self.bbox, self.epsg_code, self.geometry = self.get_bounds()
        self.collections = self.get_collections()
        self.service_base_url = list(self.collections.values())[0]["data_collection"].service_url
        self.sentinel_hub = SentinelHub(user=user, service_base_url=self.service_base_url)
        self.mimetype = self.get_mimetype()
        self.width = width or self.get_dimensions()[0]
        self.height = height or self.get_dimensions()[1]
        self.sample_type = self.get_sample_type()
        self.evalscript = self.get_evalscript()

    def convert_to_sh_bbox(self):
        return BBox(self.bbox, CRS(self.epsg_code))

    def get_evalscript(self):
        process_graph = remove_partially_supported_processes_from_process_graph(
            self.process_graph, partially_supported_processes
        )

        load_collection_nodes = self.get_all_load_collection_nodes()
        bands_metadata = {}
        for node_id, load_collection_node in load_collection_nodes.items():
            collection = collections.get_collection(load_collection_node["arguments"]["id"])
            bands = collection.get("summaries", {}).get("eo:bands")
            bands_metadata[f"node_{node_id}"] = bands

        results = convert_from_process_graph(
            process_graph,
            sample_type=self.sample_type.value,
            user_defined_processes=self.user_defined_processes,
            bands_metadata=bands_metadata,
            encode_result=False,
        )
        evalscript = results[0]["evalscript"]
        evalscript.mosaicking = self.get_appropriate_mosaicking()

        if all(
            bnds is None
            for bnds in [datasource_with_bands["bands"] for datasource_with_bands in self.get_input_bands()]
        ):
            all_bands = []
            for node_id, load_collection_node in load_collection_nodes.items():
                collection = collections.get_collection(load_collection_node["arguments"]["id"])
                all_bands.append(
                    {"datasource": f"node_{node_id}", "bands": collection["cube:dimensions"]["bands"]["values"]}
                )
            evalscript.set_input_bands(all_bands)

        return evalscript

    def get_appropriate_mosaicking(self):
        load_collection_nodes = self.get_all_load_collection_nodes()

        for _, load_collection_node in load_collection_nodes.items():
            openeo_collection = collections.get_collection(load_collection_node["arguments"]["id"])
            from_time, to_time = openeo_collection.get("extent").get("temporal")["interval"][0]

            # if any of the load_collection nodes is a "timeless collection" - return "SIMPLE" as usually all collections support at least "SIMPLE" mosaicking type
            if from_time is None and to_time is None:
                # Collection has no time extent so it's one of the "timeless" collections as e.g. DEM
                # Mosaicking: "ORBIT" or "TILE" is not supported.
                return "SIMPLE"

        return "ORBIT"

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
            load_collection_nodes = self.get_all_load_collection_nodes()
            load_collection_node = next(
                lcn for lcn in load_collection_nodes.values() if lcn["arguments"]["id"] is collection_id
            )
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

        if collection_type.startswith("hls"):
            return HLS_COLLECTION

        for data_collection in DataCollection:
            if data_collection.value.api_id == collection_type:
                return data_collection

        raise Internal(f"Collection {collection_id} could not be mapped to a Sentinel Hub collection type.")

    def get_node_by_process_id(self, process_id):
        return get_node_by_process_id(self.process_graph, process_id)

    def get_all_load_collection_nodes(self):
        return get_all_load_collection_nodes(self.process_graph)

    def get_collections(self):
        collections = {}
        load_collection_nodes = self.get_all_load_collection_nodes()
        for node_id, load_collection_node in load_collection_nodes.items():
            from_time, to_time = self.get_temporal_extent(load_collection_node)
            data_collection = self.id_to_data_collection(load_collection_node["arguments"]["id"])
            collections[f"node_{node_id}"] = {
                "data_collection": data_collection,
                "from_date": from_time,
                "to_date": to_time,
            }

        return collections

    def get_bounds_from_load_collection(self):
        """
        Returns bbox, EPSG code, geometry
        """
        load_collection_nodes = list(self.get_all_load_collection_nodes().values())
        load_collection_node = load_collection_nodes[0]
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
            if partial_processes_crs != self.DEFAULT_EPSG_CODE:
                epsg_code = partial_processes_crs
                if bbox:
                    bbox = convert_bbox_crs(bbox, self.DEFAULT_EPSG_CODE, partial_processes_crs)
                if geometry:
                    geometry = convert_geometry_crs(shape(geometry), partial_processes_crs)

            return bbox, epsg_code, geometry

        if geometry:
            geometry = shape(geometry)
        elif bbox:
            west, south, east, north = bbox
            if epsg_code != self.DEFAULT_EPSG_CODE:
                west, south = convert_to_epsg4326(epsg_code, west, south)
                east, north = convert_to_epsg4326(epsg_code, east, north)
            geometry = shape(construct_geojson(west, south, east, north))

        final_geometry = partial_processes_geometry.intersection(geometry)

        if final_geometry.is_empty:
            raise NoDataAvailable("Requested spatial extent is empty.")

        if partial_processes_crs is not None and partial_processes_crs != self.DEFAULT_EPSG_CODE:
            final_geometry = convert_geometry_crs(final_geometry, partial_processes_crs)

        return final_geometry.bounds, partial_processes_crs, mapping(final_geometry)

    def get_collection_temporal_step(self, load_collection_node):
        collection = collections.get_collection(load_collection_node["arguments"]["id"])
        if not collection:
            return None
        return collection["cube:dimensions"]["t"].get("step")

    def get_temporal_interval(self, in_days=False):
        load_collection_nodes = self.get_all_load_collection_nodes()
        temporal_intervals = {}
        for node_id, load_collection_node in load_collection_nodes.items():
            step = self.get_collection_temporal_step(load_collection_node)

            if step is None:
                temporal_intervals[node_id] = None
                continue

            temporal_interval = parse_duration(step)

            if in_days:
                n_seconds_per_day = 86400
                temporal_intervals[node_id] = temporal_interval.total_seconds() / n_seconds_per_day
                continue

            temporal_intervals[node_id] = temporal_interval.total_seconds()

        return temporal_intervals

    def get_maximum_temporal_extent_for_collection(self, load_collection_node):
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

    def get_temporal_extent(self, load_collection_node):
        """
        Returns from_time, to_time
        """
        temporal_extent = load_collection_node["arguments"].get("temporal_extent")
        if temporal_extent is None:
            temporal_extent = self.get_maximum_temporal_extent_for_collection(load_collection_node)

        interval_start, interval_end = temporal_extent
        if interval_start is None:
            from_time, _ = self.get_maximum_temporal_extent_for_collection(load_collection_node)
        else:
            from_time = parse_time(interval_start)

        if interval_end is None:
            _, to_time = self.get_maximum_temporal_extent_for_collection(load_collection_node)
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
        input_bands = []
        load_collection_nodes = self.get_all_load_collection_nodes()
        for node_id, load_collection_node in load_collection_nodes.items():
            bands = load_collection_node["arguments"].get("bands")
            input_bands.append({"datasource": "node_" + node_id, "bands": bands})
        return input_bands

    def format_to_mimetype(self, output_format):
        OUTPUT_FORMATS = self.request_type.get_supported_mime_types()
        output_format = output_format.lower()
        if output_format in OUTPUT_FORMATS:
            return OUTPUT_FORMATS[output_format]
        else:
            raise FormatUnsuitable(self.request_type.get_unsupported_mimetype_message())

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
        load_collection_nodes = self.get_all_load_collection_nodes()
        x_resolutions = []
        y_resolutions = []
        for node_id, load_collection_node in load_collection_nodes.items():
            collection = collections.get_collection(load_collection_node["arguments"]["id"])
            summaries = collection.get("summaries", {})
            selected_bands = load_collection_node["arguments"].get("bands")

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
            x_resolutions.append(min(list_of_resolutions, key=lambda x: x[0])[0])
            y_resolutions.append(min(list_of_resolutions, key=lambda x: x[1])[1])

        return (min(x_resolutions), min(y_resolutions))

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
        utm_tiling_grids = self.sentinel_hub.get_utm_tiling_grids()

        if self.pisp_resolution:
            # If desired resolution was explicitly set in partially defined spatial processes.
            # we must make sure the X and Y resolution are the same and resolution is available among existing tiling grids
            if self.pisp_resolution[0] != self.pisp_resolution[1]:
                raise BadRequest("X and Y resolution must be identical in Sentinel Hub batch processing request.")

            for tiling_grid in utm_tiling_grids:
                if self.pisp_resolution[0] in tiling_grid["properties"]["resolutions"]:
                    break
            else:
                raise BadRequest(
                    "Resolution must be one of the supported values in Sentinel Hub batch processing request."
                )
            requested_resolution = self.pisp_resolution[0]
        else:
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
            temporal_intervals = self.get_temporal_interval()

            n_dates = 0
            for node_id, temporal_interval in temporal_intervals.items():
                if temporal_interval is None:
                    n_seconds_per_day = 86400
                    default_temporal_interval = 3
                    temporal_interval = default_temporal_interval * n_seconds_per_day

                collection = self.collections[f"node_{node_id}"]
                from_date = collection["from_date"]
                to_date = collection["to_date"]

                date_diff = (to_date - from_date).total_seconds()
                n_dates += math.ceil(date_diff / temporal_interval) + 1

            n_output_bands *= n_dates * n_original_temporal_dimensions

        if self.mimetype == MimeType.PNG:
            n_output_bands = min(n_output_bands, 4)
        elif self.mimetype == MimeType.JPG:
            n_output_bands = min(n_output_bands, 3)

        return n_pixels * n_bytes * n_output_bands

    def check_if_data_fusion_possible(self):
        """
        Checks if different collections are hosted by same SH deployment
        """
        collections = [c["data_collection"] for c in self.collections.values()]
        service_urls = [c.service_url for c in collections]
        if len(set(service_urls)) > 1:
            raise DataFusionNotPossibleDifferentSHDeployments()

    def execute_sync(self):
        estimated_file_size = self.estimate_file_size()
        if estimated_file_size > self.MAXIMUM_SYNC_FILESIZE_BYTES:
            raise ProcessGraphComplexity(
                f"estimated size of generated output of {estimated_file_size} bytes exceeds maximum supported size of {self.MAXIMUM_SYNC_FILESIZE_BYTES} bytes."
            )

        if self.width == 0 or self.height == 0:
            raise ImageDimensionInvalid(self.width, self.height)

        self.check_if_data_fusion_possible()
        
        return self.sentinel_hub.create_processing_request(
            bbox=self.bbox,
            epsg_code=self.epsg_code,
            geometry=self.geometry,
            collections=self.collections,
            evalscript=self.evalscript.write(),
            width=self.width,
            height=self.height,
            mimetype=self.mimetype,
            resampling_method=self.pisp_resampling_method,
        )

    def create_batch_job(self):
        self.tiling_grid_id, self.tiling_grid_resolution = self.get_appropriate_tiling_grid_and_resolution()

        self.check_if_data_fusion_possible()

        return (
            self.sentinel_hub.create_batch_job(
                bbox=self.bbox,
                epsg_code=self.epsg_code,
                geometry=self.geometry,
                collections=self.collections,
                evalscript=self.evalscript.write(),
                tiling_grid_id=self.tiling_grid_id,
                tiling_grid_resolution=self.tiling_grid_resolution,
                mimetype=self.mimetype,
                resampling_method=self.pisp_resampling_method,
            ),
            self.service_base_url,
        )
