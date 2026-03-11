"""
REST scraper backend — query JSON APIs via directives.

Directive format:
  use: rest
  site: https://api.example.com/data
  method: GET  # optional, default is GET
  headers:     # optional
    Authorization: "Bearer ${TOKEN}"
  body:        # optional, sent as JSON for POST/PUT
    key: val

  scrape:
    name: { path: data.user.name }
    id:   { path: data.user.id }
"""

import requests
from datetime import datetime
from scraper.scrapers.graphql_scraper import _get_path


def scrape(dados: dict) -> dict:
    method  = str(dados.get("method", "GET")).upper()
    headers = {"Content-Type": "application/json", **(dados.get("headers") or {})}
    body    = dados.get("body")
    timeout = dados.get("timeout", 15)
    site    = dados["site"]

    resp = requests.request(
        method=method,
        url=site,
        json=body if body and method in ("POST", "PUT", "PATCH") else None,
        headers=headers,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()

    result = {}
    for key, spec in dados.get("scrape", {}).items():
        if isinstance(spec, dict):
            path = spec.get("path", key)
        elif isinstance(spec, list) and spec:
            path = spec[0] if isinstance(spec[0], str) else key
        else:
            path = key
        
        # Support 'all' if the dot path points to a list? 
        # For now, let's stick to the basic _get_path behavior.
        result[key] = _get_path(data, path)

    result["url"] = site
    result["timestamp"] = datetime.now()
    return result
