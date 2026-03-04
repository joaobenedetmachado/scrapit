"""
Notifications — send alerts when changes are detected.

Supported channels:
  - webhook: POST JSON payload to a URL
  - console: print to stdout (always active if changes found)

Configure in directive:
  notify:
    webhook: https://hooks.example.com/...
    on_change_only: true   # default true

Or via environment variable SCRAPIT_WEBHOOK_URL.
"""

import json
from scraper.logger import log


def _build_payload(directive: str, result: dict, changes: dict) -> dict:
    return {
        "event": "scrapit.change_detected",
        "directive": directive,
        "url": result.get("url"),
        "timestamp": str(result.get("timestamp")),
        "changes": {
            field: {"old": str(vals["old"]), "new": str(vals["new"])}
            for field, vals in changes.items()
        },
    }


def notify(
    directive_name: str,
    result: dict,
    changes: dict,
    notify_config: dict | None = None,
):
    if not changes:
        return

    payload = _build_payload(directive_name, result, changes)

    # Console
    print("\n[CHANGE DETECTED]")
    for field, vals in changes.items():
        print(f"  {field}:")
        print(f"    before: {vals['old']}")
        print(f"    after : {vals['new']}")

    # Webhook
    cfg = notify_config or {}
    webhook_url = cfg.get("webhook") or _env_webhook()
    if webhook_url:
        _send_webhook(webhook_url, payload)


def _env_webhook() -> str | None:
    import os
    return os.getenv("SCRAPIT_WEBHOOK_URL")


def _send_webhook(url: str, payload: dict):
    try:
        import requests
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        log(f"webhook sent → {url} ({resp.status_code})")
    except Exception as e:
        log(f"webhook failed [{url}]: {e}", "error")
