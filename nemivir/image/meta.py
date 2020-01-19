from abc import ABC, abstractmethod
from typing import List
from warnings import warn

from pymongo import MongoClient, IndexModel, DESCENDING, ASCENDING, HASHED


class AbstractImageMeta(ABC):
    @abstractmethod
    def list_hashes(self, limit: int = -1) -> List[str]: pass

    @abstractmethod
    def list_images(self, image_hash: str, limit: int = -1) -> List[dict]:
        """
        List all images info
        :param limit:
        :param image_hash:
        :return: dict field definitions
            (* -> option, but better to have, ** -> option)
            image_hash
            fid(_id)
            *file_size
            *width
            *height
            *channel
            *mode
            **gps_point
            **urls
        """
        pass

    @abstractmethod
    def add_image(self, image_hash: str, fid: str, **kwargs): pass

    @abstractmethod
    def remove_image(self, fid: str): pass

    @abstractmethod
    def remove_hash(self, image_hash: str) -> int: pass


class MongoDBMeta(AbstractImageMeta):
    def __init__(self, mongodb_url: str, db_name: str, collection_name: str):
        self.collection_name = collection_name
        self.db_name = db_name
        self._conn: MongoClient = MongoClient(mongodb_url)
        self._get_collection().create_indexes([
            IndexModel([("image_hash", HASHED)]),
            IndexModel([("fid", ASCENDING)], unique=True),
        ])

    def _get_collection(self):
        return self._conn.get_database(self.db_name).get_collection(self.collection_name)

    def list_hashes(self, limit: int = -1) -> List[str]:
        if limit > 0:
            warn("Can't limit hash count while using mongo backend")
        return self._get_collection().distinct("image_hash")

    def list_images(self, image_hash: str, limit: int = -1) -> List[dict]:
        result_set = self._get_collection().find({"image_hash": image_hash})
        if limit > 0:
            result_set = result_set.limit(limit)
        return list(result_set)

    def add_image(self, image_hash: str, fid: str, **kwargs):
        return self._get_collection().insert_one(dict(
            image_hash=image_hash,
            fid=fid,
            **kwargs
        ))

    def remove_image(self, fid: str):
        doc = self._get_collection().find_one({"fid": fid})
        if doc is None:
            raise KeyError("Can't find log which fid={}".format(fid))
        dc = self._get_collection().delete_one({"fid": fid}).deleted_count
        if dc <= 0:
            raise Exception("Can't delete log {}".format(str(doc)))

    def remove_hash(self, image_hash: str) -> int:
        return self._get_collection().delete_many(
            {"image_hash": image_hash}
        ).deleted_count
