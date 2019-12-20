import os

from nemivir.image import WeedFiler
from redis import ConnectionPool

# REDIS_SERVER
# redis://[:password]@host:port/db
redis_connection_pool = [
    {"connection_pool": ConnectionPool.from_url(os.environ["REDIS_SERVER"])},
]

# FILER_SERVER
# protocal://host:port/
filer_server = WeedFiler(filer_node=os.environ["FILER_SERVER"])
