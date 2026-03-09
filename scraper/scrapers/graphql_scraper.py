"""
GraphQL scraper backend — query GraphQL APIs via directives.

Directive format:
  use: graphql
  site: https://api.example.com/graphql

  graphql:
    query: |
      query { viewer { login } }
    variables: {}           # optional
    headers:
      Authorization: "Bearer ${TOKEN}"

  scrape:
    login: { path: data.viewer.login }
    count: { path: data.repo.issues.totalCount }
"""

import requests
from datetime import datetime


def _get_path(data: dict, path: str):
    """Traverse dot-notation path in a nested dict."""
    parts = path.split(".")
    val = data
    for part in parts:
        if not isinstance(val, dict):
            return None
        val = val.get(part)
    return val


def scrape(dados: dict) -> dict:
    gql = dados.get("graphql") or {}
    query     = gql.get("query", "")
    variables = gql.get("variables") or {}
    headers   = {"Content-Type": "application/json", **(dados.get("headers") or {}), **(gql.get("headers") or {})}
    timeout   = dados.get("timeout", 15)

    resp = requests.post(
        dados["site"],
        json={"query": query, "variables": variables},
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
        result[key] = _get_path(data, path)

    result["url"] = dados["site"]
    result["timestamp"] = datetime.now()
    return result
