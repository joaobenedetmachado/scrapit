import re
from scraper.config import MONGO_URI, MONGO_DATABASE, MONGO_COLLECTION
from scraper.logger import log


class MongoStorage:
    def __init__(self):
        self._client = None
        self._collection = None

    def _connect(self):
        if self._collection is not None:
            return
        from pymongo import MongoClient
        self._client = MongoClient(MONGO_URI)
        db = self._client[MONGO_DATABASE]
        self._collection = db[MONGO_COLLECTION]

    def save(self, data: dict) -> str:
        if not isinstance(data, dict):
            raise TypeError(f"save expected dict, got {type(data)}")
        self._connect()
        try:
            self._collection.insert_one(data)
            return "added to database"
        except Exception as e:
            log(f"error inserting in database: {e}", "error")
            return "error in storage"

    def find_by_url(self, pattern: str) -> list:
        self._connect()
        escaped = re.escape(pattern)
        regex = re.compile(rf"^{escaped}", re.IGNORECASE)
        return list(self._collection.find({"url": regex}))

    def find_by_field(self, field: str, pattern: str) -> list:
        self._connect()
        try:
            escaped = re.escape(pattern)
            regex = re.compile(rf"^{escaped}", re.IGNORECASE)
            return list(self._collection.find({field: regex}))
        except Exception as e:
            log(f"error querying field {field}: {e}", "error")
            return []


_default = MongoStorage()


def save_scraped(data: dict) -> str:
    return _default.save(data)


def get_elements_by_site(name: str) -> list:
    return _default.find_by_url(name)


def get_elements_by_part(name: str, part: str) -> list:
    return _default.find_by_field(part, name)
