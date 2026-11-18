from prometheus_client import Counter, Histogram

# Total cache hits and misses
CACHE_REQUESTS = Counter(
    "ecommerce_cache_requests_total",
"Total cache requests",
["api", "result"],
)

# Time spent performing Redis cache operations
CACHE_OPERATION_DURATION = Histogram(
    "ecommerce_cache_operation_duration_seconds",
    "Duration of Redis cache operations",
    ["api", "operation"],
    buckets=(
        0.001,    # 1 ms
        0.002,    # 2 ms
        0.005,    # 5 ms
        0.010,    # 10 ms
        0.015,    # 15 ms
        0.020,    # 20 ms
        0.025,    # 25 ms
        0.050,    # 50 ms
        0.075,    # 75 ms
        0.100,    # 100 ms
        0.250,    # 250 ms
        0.500,    # 500 ms
        0.750,    # 750 ms
        1.000,    # 1 sec
        2.000,    # 2 sec
    ),
)

# Total cache invalidation operations
CACHE_INVALIDATIONS = Counter(
    "ecommerce_cache_invalidations_total",
    "Total cache invalidation operations",
    ["api", "operation"],
)


