import warnings
from datetime import datetime, date, timedelta, timezone

from sentinelhub import DataCollection, MimeType
from sentinelhub.time_utils import parse_time
from pg_to_evalscript import convert_from_process_graph

from processing.openeo_process_errors import FormatUnsuitable
from processing.sentinel_hub import SentinelHub


class Process:
    def __init__(self, process):
        self.DEFAULT_EPSG_CODE = 4326
        self.DEFAULT_WIDTH = 100
        self.DEFAULT_HEIGHT = 100
        self.sentinel_hub = SentinelHub()

        self.process_graph = process["process_graph"]

        self.evalscript = self.get_evalscript()
        self.bbox, self.epsg_code, self.geometry = self.get_bounds()
        self.collection = self.get_collection()
        self.from_date, self.to_date = self.get_temporal_extent()
        self.mimetype = self.get_mimetype()
        self.width, self.height = self.get_dimensions()

    def get_evalscript(self):
        results = convert_from_process_graph(self.process_graph, encode_result=False)
        return results[0]["evalscript"].write()

    def id_to_data_collection(self, collection_id):
        warnings.warn("id_to_data_collection not implemented yet!")
        return DataCollection.SENTINEL2_L1C

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
            return (0, -90, 360, 90), self.DEFAULT_EPSG_CODE, None
        elif (
            isinstance(spatial_extent, dict)
            and "type" in spatial_extent
            and spatial_extent["type"] in ("Polygon", "MultiPolygon")
        ):
            return None, self.DEFAULT_EPSG_CODE, spatial_extent
        else:
            epsg_code = spatial_extent.get("crs", self.DEFAULT_EPSG_CODE)
            east = spatial_extent["east"]
            west = spatial_extent["west"]
            north = spatial_extent["north"]
            south = spatial_extent["south"]
            return (west, south, east, north), epsg_code, None

    def get_maximum_temporal_extent_for_collection(collection):
        warnings.warn("get_maximum_temporal_extent_for_collection not implemented yet!")
        return datetime.now(), datetime.now()

    def get_temporal_extent(self):
        """
        Returns from_time, to_time
        """
        load_collection_node = self.get_node_by_process_id("load_collection")
        temporal_extent = load_collection_node["arguments"]["temporal_extent"]
        if temporal_extent is None:
            from_time, to_time = self.get_maximum_temporal_extent_for_collection(self.collection)
            return from_time, to_time

        interval_start, interval_end = temporal_extent
        if interval_start is None:
            from_time, _ = self.get_maximum_temporal_extent_for_collection(self.collection)
        else:
            from_time = parse_time(interval_start)

        if interval_end is None:
            _, to_time = self.get_maximum_temporal_extent_for_collection(self.collection)
        else:
            to_time = parse_time(interval_end)

        # type(d) is date is used because Datetime is a subclass of Date and isinstance(d, Date) is always True
        if type(from_time) is date:
            from_time = datetime(from_time.year, from_time.month, from_time.day)
        if type(to_time) is date:
            to_time = datetime(to_time.year, to_time.month, to_time.day) + timedelta(days=1)

        if from_time.tzinfo is None:
            from_time = from_time.replace(tzinfo=timezone.utc)
        if to_time.tzinfo is None:
            to_time = to_time.replace(tzinfo=timezone.utc)

        to_time = to_time - timedelta(milliseconds=1)  # End of the interval is not inclusive
        return from_time, to_time

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

    def get_dimensions(self):
        warnings.warn("get_dimensions_from_process_graph when width and height are not specified not implemented yet!")
        load_collection_node = self.get_node_by_process_id("load_collection")
        spatial_extent = load_collection_node["arguments"]["spatial_extent"]

        if spatial_extent is None:
            return self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT

        width = spatial_extent.get("width", self.DEFAULT_WIDTH)
        height = spatial_extent.get("height", self.DEFAULT_HEIGHT)
        return width, height

    def execute_sync(self):
        return self.sentinel_hub.create_processing_request(
            bbox=self.bbox,
            epsg_code=self.epsg_code,
            geometry=self.geometry,
            collection=self.collection,
            evalscript=self.evalscript,
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
            evalscript=self.evalscript,
            from_date=self.from_date,
            to_date=self.to_date,
            width=self.width,
            height=self.height,
            mimetype=self.mimetype,
        )
