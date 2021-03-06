import logging
import time

from redis import StrictRedis

from nemivir.protos import ImageResponse

log = logging.getLogger(__file__)


class RedisImageCache:
    def __init__(
            self,
            redis_client: StrictRedis,
            default_ttl: float,
            key_prefix: str = "imc"
    ):
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl
        self.redis_client = redis_client

    def _generate_key(self, filename: str, key: str):
        return "{}_{}_{}".format(
            self.key_prefix,
            filename,
            key,
        )

    def put(self, filename: str, key: str, value: ImageResponse, ttl: int = None):
        if ttl is None:
            ttl = self.default_ttl
        self.redis_client.setex(self._generate_key(filename, key), ttl, value.SerializeToString())

    def get(self, filename: str, key: str) -> ImageResponse:
        fk = self._generate_key(filename, key)
        if self.redis_client.exists(fk):
            resp = ImageResponse()
            resp.ParseFromString(self.redis_client.get(fk))
            return resp
        else:
            raise KeyError("Can't find key {} in redis".format(fk))

    def _clean_by_pattern(self, pattern: str, batch_count: int = 100):
        log.info("Cleaning by pattern: {}".format(pattern))

        def delete_keys(items):
            pipeline = self.redis_client.pipeline()
            for item in items:
                pipeline.delete(item)
                log.debug("Removing item {}".format(item))
            pipeline.execute()
            time.sleep(0.01)

        keys = []
        for key in self.redis_client.scan_iter(pattern, count=batch_count):
            keys.append(key)
            if len(keys) >= batch_count:
                delete_keys(keys)
                keys = []
        delete_keys(keys)

    def clean(self, filename: str, key: str = None):
        if key is None:
            self._clean_by_pattern(self._generate_key(filename, "*"))
        else:
            self.redis_client.delete(self._generate_key(filename, key))

    def clean_hash(self, image_hash: str):
        self._clean_by_pattern("{}_{}*".format(self.key_prefix, image_hash))

    def clean_all(self):
        self._clean_by_pattern("{}_*".format(self.key_prefix))
