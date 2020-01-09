import os

from redis import ConnectionPool, StrictRedis

from nemivir.image import WeedFiler
# REDIS_SERVER
# redis://[:password]@host:port/db
from nemivir.util.cache import RedisImageCache

client = ConnectionPool.from_url(os.environ["REDIS_SERVER"])
redis_connection_pool = [
    {"connection_pool": client},
]

# FILER_SERVER
# protocal://host:port/
filer_server = WeedFiler(filer_node=os.environ["FILER_SERVER"])

cache = RedisImageCache(
    redis_client=StrictRedis.from_url(os.environ["REDIS_SERVER"]),
    default_ttl=float(os.environ.get("IMG_CACHE_TIMEOUT", "1800")),
    key_prefix="nimc"
)
# max_size=int(os.environ.get("IMG_CACHE_SIZE", "512"))
