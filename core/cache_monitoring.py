import time

from django.core.cache import cache
from core.metrics import (
CACHE_REQUESTS,
CACHE_OPERATION_DURATION
)

def monitored_cache_get(api_name, cache_key):
    start_time = time.perf_counter()

    try:
        cached_data = cache.get(cache_key)
        result = 'hit' if cached_data is not None else 'miss'

        CACHE_REQUESTS.labels(api=api_name, result=result).inc()

        return cached_data

    finally:
        CACHE_OPERATION_DURATION.labels(
            api=api_name, operation="get"
        ).observe(time.perf_counter() - start_time)

def monitored_cache_set(api_name, cache_key, value, timeout=None):
    start_time = time.perf_counter()

    try:
        return cache.set(cache_key, value, timeout=timeout)
    finally:
        CACHE_OPERATION_DURATION.labels(
            api=api_name, operation="set"
        ).observe(time.perf_counter() - start_time)