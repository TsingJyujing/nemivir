import os

from redis import ConnectionPool, StrictRedis

from nemivir.image import WeedFileSystem, AbstractFileSystem, MongoDBMeta, AbstractImageMeta
# REDIS_SERVER
# redis://[:password]@host:port/db
from nemivir.util import RedisImageCache

client = ConnectionPool.from_url(os.environ["REDIS_SERVER"])
redis_connection_pool = [
    {"connection_pool": client},
]

# MASTER_SERVER
# protocal://host:port/
filesystem: AbstractFileSystem = WeedFileSystem(os.environ["MASTER_SERVER"])

metadb: AbstractImageMeta = MongoDBMeta(os.environ["MONGODB_META"], "nemivir", "image_meta")

cache = RedisImageCache(
    redis_client=StrictRedis.from_url(os.environ["REDIS_SERVER"]),
    default_ttl=int(os.environ.get("IMG_CACHE_TIMEOUT", "1800")),
    key_prefix="nimc"
)
