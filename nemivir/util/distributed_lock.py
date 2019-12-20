import random
import string

from redlock import Redlock

CHARACTERS = string.ascii_letters + string.digits


class RedisDistributedLock:
    def __init__(self, redis_lock: Redlock, lock_key: str, ttl: int = 30):
        """
        A context based redis distributed lock
        :param redis_lock: Redlock object
        :param lock_key: the resource key to lock
        :param ttl: timout after ttl seconds
        """
        self._rlk = redis_lock
        self._key = lock_key
        self._ttl = ttl
        self._lock = None

    def __enter__(self):
        self._lock = self._rlk.lock(self._key, self._ttl)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._rlk.unlock(self._lock)


def get_random_string(size: int):
    """
    Get a random string combined by a-z,A-Z,0-9
    :param size:
    :return:
    """
    return ''.join(random.choice(CHARACTERS) for _ in range(size))
