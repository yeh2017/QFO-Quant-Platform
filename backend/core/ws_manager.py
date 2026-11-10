"""
WebSocket 广播代理 — 回调注入模式
=================================
底层模块(utils/jobs/services)通过此模块发送 WS 消息，
无需直接依赖 routers.ws，消除跨层反向导入。

启动时由 main.py 注入实际的 broadcast 函数。
"""

from typing import Callable, Optional

_broadcast_fn: Optional[Callable[[dict], None]] = None


def set_broadcaster(fn: Callable[[dict], None]):
    """启动时注入实际的广播实现（main.py 调用一次）"""
    global _broadcast_fn
    _broadcast_fn = fn


def broadcast_threadsafe(message: dict):
    """线程安全广播 — 各层统一调用入口，未注入时静默跳过"""
    if _broadcast_fn is not None:
        _broadcast_fn(message)
