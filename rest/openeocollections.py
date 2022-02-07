import requests

from logging import log, ERROR


class CollectionsProvider:
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
        return collections


class Collections:
    def __init__(self):
        self.providers = [
            CollectionsProvider("edc", "https://collections.eurodatacube.com/stac/index.json"),
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
