import os
import glob
import json
import copy

import requests

from logging import log, ERROR

# aliases for harmonized Sentinel-2 collection names to platform names
SH_COLLECTION_ID_ALIASES = {
    "SENTINEL2_L2A_SENTINELHUB": "SENTINEL2_L2A",
    "SENTINEL2_L1C_SENTINELHUB": "SENTINEL2_L1C",
}


class CollectionsProvider:
    def __init__(self, id, url=None, directory=None):
        self.id = id
        self.url = url
        self.directory = directory

    def load_collections(self):
        all_collections = []
        if self.url is not None:
            all_collections.extend(self.load_collections_from_url())
        if self.directory is not None:
            all_collections.extend(self.load_collections_from_directory())
        return all_collections

    def load_collections_from_directory(self):
        script_dir = os.path.dirname(__file__)
        abs_filepath = os.path.join(script_dir, self.directory)

        collections = []

        for file in glob.iglob(f"{abs_filepath}/*.json"):
            with open(file) as f:
                output_format = os.path.splitext(os.path.basename(file))[0]
                collections.append(json.load(f))

        return collections

    def load_collections_from_url(self):
        collections = []

        r = requests.get(
            self.url,
        )

        if r.status_code != 200:
            log(ERROR, f"Unable to load collections:  {r.status_code} {r.text}")

        else:
            collections_meta_data = r.json()
            for collection_meta_data in collections_meta_data:
                # load each collection
                collection = requests.get(collection_meta_data["link"])
                if collection.status_code != 200:
                    log(
                        ERROR,
                        f"Unable to load collection: {collection_meta_data['id']} {collection.status_code} {collection.text}",
                    )
                else:
                    collections.append(collection.json())
                    if SH_COLLECTION_ID_ALIASES.get(collection_meta_data["id"]):
                        alias_collection = copy.deepcopy(collection.json())
                        alias_collection["id"] = SH_COLLECTION_ID_ALIASES.get(collection_meta_data["id"])
                        collections.append(alias_collection)

        return collections


class Collections:
    def __init__(self):
        self.providers = [
            CollectionsProvider("edc", url="https://collections.eurodatacube.com/stac/index.json"),
            CollectionsProvider("commercial-data", directory="./commercial_collections"),
        ]
        self.collections_cache = {}

    def load(self):
        for provider in self.providers:
            collections = provider.load_collections()
            for collection in collections:
                self.collections_cache[collection["id"]] = collection

    def check_if_loaded(self):
        if not self.collections_cache:
            self.load()

    def get_collections(self):
        self.check_if_loaded()
        return self.collections_cache

    def set_collections(self, collections):
        self.collections_cache = collections

    def get_collections_basic_info(self):
        self.check_if_loaded()
        collections_basic_info = map(
            lambda collection_info: {
                "stac_version": collection_info["stac_version"],
                "id": collection_info["id"],
                "description": collection_info["description"],
                "license": collection_info["license"],
                "extent": collection_info["extent"],
                "links": collection_info["links"],
            },
            self.collections_cache.values(),
        )

        return list(collections_basic_info)

    def get_collection(self, collection_id):
        self.check_if_loaded()
        return self.collections_cache.get(collection_id)


collections = Collections()
