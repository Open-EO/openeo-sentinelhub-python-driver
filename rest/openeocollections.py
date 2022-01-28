import glob
import json
import requests

from abc import ABC, abstractmethod
from logging import log, INFO, WARN, ERROR


class CollectionsProvider(ABC):
    @abstractmethod
    def load_collections(self):
        pass


class URLCollectionsProvider(CollectionsProvider):
    def __init__(self, id, url):
        self.id = id
        self.url = url

    def load_collections(self):
        collections = []

        r = requests.get(
            self.url,
        )

        if r.status_code != 200:
            log(ERROR, f"Unable to load collections:  {r.status_code} {r.text}")

        else:
            collectionsMetaData = r.json()

            for collectionMetaData in collectionsMetaData:
                # load each collection
                collection = requests.get(collectionMetaData["link"])
                if collection.status_code != 200:
                    log(
                        ERROR,
                        f"Unable to load collection: {collectionMetaData['id']} {collection.status_code} {collection.text}",
                    )
                else:
                    collections.append(collection.json())
        return collections


class LocalJSONCollectionsProvider(CollectionsProvider):
    def __init__(self, folder):
        self.folder = folder

    def load_collections(self):
        collections = []

        files = glob.iglob(self.folder)

        for file in files:
            with open(file) as f:
                data = json.load(f)
                collections.append(data)

        return collections


class Collections:
    def __init__(self):
        self.providers = [
            LocalJSONCollectionsProvider("collection_information/*.json"),
            URLCollectionsProvider("edc", "https://collections.eurodatacube.com/stac/index.json"),
        ]
        self.collections_cache = {}

    def load(self):
        for provider in self.providers:
            collections = provider.load_collections()
            for collection in collections:
                self.collections_cache[collection["id"]] = collection

    def get_collections(self):
        if not self.collections_cache:
            self.load()

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
        if not self.collections_cache:
            self.load()

        collection = self.collections_cache.get(collection_id)
        return collection


collections = Collections()
