import os
import sys

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
except ImportError:
    Counter = Histogram = Gauge = None
    generate_latest = None
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"

_metrics_init = False

# Metric instruments
scrapit_scrape_total = None
scrapit_scrape_duration_seconds = None
scrapit_fields_coverage = None


def init_metrics():
    """Initializes Prometheus metrics instruments if client is available."""
    global _metrics_init, scrapit_scrape_total, scrapit_scrape_duration_seconds, scrapit_fields_coverage
    if _metrics_init or Counter is None:
        return

    scrapit_scrape_total = Counter(
        "scrapit_scrape_total",
        "Total scrapes by directive",
        ["directive", "status"]
    )
    scrapit_scrape_duration_seconds = Histogram(
        "scrapit_scrape_duration_seconds",
        "Duration of scrapes in seconds",
        ["directive"]
    )
    scrapit_fields_coverage = Gauge(
        "scrapit_fields_coverage",
        "Fields coverage percentage (0.0 to 1.0)",
        ["directive"]
    )
    _metrics_init = True


def track_scrape(stats):
    """Update metrics based on ScrapeStats."""
    init_metrics()
    if Counter is None:
        return

    status = "error" if stats.errors else "ok"
    scrapit_scrape_total.labels(directive=stats.directive, status=status).inc()
    
    if stats.elapsed > 0:
        scrapit_scrape_duration_seconds.labels(directive=stats.directive).observe(stats.elapsed)

    total = stats.fields_found + stats.fields_missing
    if total > 0:
        coverage = stats.fields_found / total
        scrapit_fields_coverage.labels(directive=stats.directive).set(coverage)


def get_metrics_content() -> bytes:
    """Returns the latest Prometheus exposition output or basic warning message if disabled."""
    init_metrics()
    if generate_latest is None:
        return b"# prometheus_client not installed\n"
    return generate_latest()
