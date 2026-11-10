"""
因子计算 TTL 缓存（共享状态）
============================
从 routers/factors.py 下沉到 utils 层，
使 jobs/cleanup_job.py 无需反向导入 routers。
"""

import time
import threading

factor_cache: dict = {}
factor_cache_lock = threading.Lock()
FACTOR_TTL = 300  # 5分钟


def cache_key(codes, start_date, end_date, selected_factors, factor_weights=None):
    return hash((
        tuple(sorted(codes)),
        start_date, end_date,
        tuple(sorted((selected_factors or {}).items())),
        tuple(sorted((factor_weights or {}).items())),
    ))


def cache_get(key):
    with factor_cache_lock:
        entry = factor_cache.get(key)
        if entry and (time.time() - entry['ts']) < FACTOR_TTL:
            return entry['data']
        return None


def cache_set(key, data):
    with factor_cache_lock:
        factor_cache[key] = {'data': data, 'ts': time.time()}
        if len(factor_cache) > 100:
            oldest = min(factor_cache, key=lambda k: factor_cache[k]['ts'])
            del factor_cache[oldest]


def cleanup_expired():
    """清理过期缓存条目，返回清理数量"""
    now = time.time()
    with factor_cache_lock:
        expired_keys = [
            k for k, entry in list(factor_cache.items())
            if now - entry.get('ts', 0) > FACTOR_TTL
        ]
        for k in expired_keys:
            del factor_cache[k]
    return len(expired_keys)
