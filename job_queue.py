import os
from redis import Redis
from rq import Queue


def queue_enabled() -> bool:
    return bool(os.getenv("REDIS_URL"))


def get_redis() -> Redis | None:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return None
    return Redis.from_url(redis_url)


def get_queue(name: str = "automations") -> Queue | None:
    redis_conn = get_redis()
    if not redis_conn:
        return None
    return Queue(name, connection=redis_conn, default_timeout=900)
