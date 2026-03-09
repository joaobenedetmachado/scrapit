"""
Proxy pool — round-robin or random rotation for directives with multiple proxies.

Directive usage:
  proxies:
    - http://proxy1:8080
    - http://proxy2:8080
  proxy_strategy: round_robin   # or: random (default: round_robin)
"""

import random
import threading


class ProxyPool:
    def __init__(self, proxies: list[str], strategy: str = "round_robin"):
        self._proxies = list(proxies)
        self._strategy = strategy
        self._index = 0
        self._lock = threading.Lock()
        self._failed: set[str] = set()

    def next(self) -> str | None:
        available = [p for p in self._proxies if p not in self._failed]
        if not available:
            self._failed.clear()
            available = list(self._proxies)
        if not available:
            return None
        if self._strategy == "random":
            return random.choice(available)
        with self._lock:
            proxy = available[self._index % len(available)]
            self._index += 1
        return proxy

    def mark_failed(self, proxy: str):
        self._failed.add(proxy)


def from_directive(dados: dict) -> "ProxyPool | None":
    proxies = dados.get("proxies")
    if not proxies or not isinstance(proxies, list):
        return None
    strategy = dados.get("proxy_strategy", "round_robin")
    return ProxyPool(proxies, strategy)
