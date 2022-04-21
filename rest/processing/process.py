import warnings
from datetime import datetime, date, timezone, timedelta

from sentinelhub import DataCollection, MimeType, BBox, Geometry, CRS
from sentinelhub.time_utils import parse_time
from pg_to_evalscript import convert_from_process_graph
from sentinelhub.geo_utils import bbox_to_dimensions

from processing.openeo_process_errors import FormatUnsuitable
from processing.sentinel_hub import SentinelHub
from processing.const import SampleType, default_sample_type_for_mimetype, supported_sample_types
from openeocollections import collections
from openeoerrors import CollectionNotFound, Internal, ProcessParameterInvalid
from processing.utils import is_geojson, validate_geojson, parse_geojson
from openeoerrors import CollectionNotFound, Internal, TemporalExtentError


class Process:
    def __init__(self, process, width=None, height=None):
        self.DEFAULT_EPSG_CODE = 4326
        self.DEFAULT_RESOLUTION = (10, 10)
        self.sentinel_hub = SentinelHub()

        self.process_graph = process["process_graph"]
        self.bbox, self.epsg_code, self.geometry = self.get_bounds()
        self.collection = self.get_collection()
        self.from_date, self.to_date = self.get_temporal_extent()
        self.mimetype = self.get_mimetype()
        self.width = width or self.get_dimensions()[0]
        self.height = height or self.get_dimensions()[1]
        self.sample_type = self.get_sample_type()
        self.evalscript = self.get_evalscript()

    def convert_to_sh_bbox(self):
        return BBox(self.bbox, CRS(self.epsg_code))

    def get_evalscript(self):
        results = convert_from_process_graph(
            self.process_graph, sample_type=self.sample_type.value, encode_result=False
        )
        evalscript = results[0]["evalscript"]

        if self.get_input_bands() is None:
            load_collection_node = self.get_node_by_process_id("load_collection")
            collection = collections.get_collection(load_collection_node["arguments"]["id"])
            all_bands = collection["cube:dimensions"]["bands"]["values"]
            evalscript.set_input_bands(all_bands)

        return evalscript

    def id_to_data_collection(self, collection_id):
        collection_info = collections.get_collection(collection_id)

        if not collection_info:
            raise CollectionNotFound()

        collection_type = collection_info["datasource_type"]

        if collection_type.startswith("byoc"):
            byoc_collection_id = collection_type.replace("byoc-", "")
            service_url = next(
                provider["url"] for provider in collection_info["providers"] if "processor" in provider["roles"]
            )
            return DataCollection.define_byoc(byoc_collection_id, service_url=service_url)

        if collection_type.startswith("batch"):
            batch_collection_id = collection_type.replace("batch-", "")
            service_url = next(
                provider["url"] for provider in collection_info["providers"] if "processor" in provider["roles"]
            )
            return DataCollection.define_batch(batch_collection_id, service_url=service_url)

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

    def get_bounds(self):
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
        spatial_extent = self.bbox
        bbox = self.convert_to_sh_bbox()
        resolution = self.get_highest_resolution()
        width, height = bbox_to_dimensions(bbox, resolution)
        return width, height

    def get_highest_resolution(self):
        load_collection_node = self.get_node_by_process_id("load_collection")
        collection = collections.get_collection(load_collection_node["arguments"]["id"])
        selected_bands = self.get_input_bands()

        if selected_bands is None:
            selected_bands = collection["cube:dimensions"]["bands"]["values"]

        bands_summaries = collection.get("summaries", {}).get("eo:bands")
        if bands_summaries is None:
            return self.DEFAULT_RESOLUTION

        list_of_resolutions = [
            band_summary.get("openeo:gsd", {}).get("value", self.DEFAULT_RESOLUTION)
            for band_summary in bands_summaries
            if band_summary["name"] in selected_bands
        ]
        highest_x_resolution = min(list_of_resolutions, key=lambda x: x[0])[0]
        highest_y_resolution = min(list_of_resolutions, key=lambda x: x[1])[1]
        return (highest_x_resolution, highest_y_resolution)

    def execute_sync(self):
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
            width=self.width,
            height=self.height,
            mimetype=self.mimetype,
        )
