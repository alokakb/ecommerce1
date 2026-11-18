from django.core.cache import cache

PRODUCT_SEARCH_VERSION_KEY = 'catalog:product_search_filter:version'

def invalidate_category_drilldown_cache():
    # invalidate all category drill down cache keys
    cache.delete_pattern('catalog:category_drill_down_*')

def invalidate_category_cache():
    # invalidate global menu
    cache.delete('catalog:global_menu:v1')
    # invalidate all category drill down cache keys
    invalidate_category_drilldown_cache()

def invalidate_product_cache(product_id):
    cache.delete(f'catalog:product_detail:{product_id}:v1')

def invalidate_product_variant_cache(product_id, variant_id):
    cache.delete(f'catalog:product_variant_detail:product_{product_id}:variant_{variant_id}:v1')
    invalidate_product_cache(product_id)

def get_product_search_version():
    version = cache.get(PRODUCT_SEARCH_VERSION_KEY)
    if version is None:
        cache.add(PRODUCT_SEARCH_VERSION_KEY, 1, timeout=None)
        version = cache.get(PRODUCT_SEARCH_VERSION_KEY)
    return version

def invalidate_product_search_cache():
    get_product_search_version()
    cache.incr(PRODUCT_SEARCH_VERSION_KEY)

