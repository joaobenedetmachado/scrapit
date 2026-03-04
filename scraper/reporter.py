"""
Scrape reporter — collects timing and field coverage stats, formats summary.
"""

import time
from dataclasses import dataclass, field


@dataclass
class ScrapeStats:
    directive: str
    url: str = ""
    pages_scraped: int = 0
    urls_scraped: int = 0
    fields_found: int = 0
    fields_missing: int = 0
    elapsed: float = 0.0
    errors: list[str] = field(default_factory=list)
    _start: float = field(default_factory=time.time, repr=False)

    def stop(self):
        self.elapsed = time.time() - self._start

    @property
    def coverage_pct(self) -> float:
        total = self.fields_found + self.fields_missing
        return (self.fields_found / total * 100) if total else 0.0

    def summary(self) -> str:
        coverage_bar = _bar(self.coverage_pct)
        lines = [
            "",
            f"  ┌─ Scrape Report ──────────────────────────────────",
            f"  │  directive   : {self.directive}",
            f"  │  url         : {self.url}",
        ]
        if self.pages_scraped > 1:
            lines.append(f"  │  pages       : {self.pages_scraped}")
        if self.urls_scraped > 1:
            lines.append(f"  │  urls scraped: {self.urls_scraped}")
        total = self.fields_found + self.fields_missing
        lines += [
            f"  │  coverage    : {coverage_bar} {self.fields_found}/{total} ({self.coverage_pct:.0f}%)",
            f"  │  duration    : {self.elapsed:.2f}s",
        ]
        if self.errors:
            lines.append(f"  │  errors      : {len(self.errors)}")
            for e in self.errors[:3]:
                lines.append(f"  │    ✗ {e}")
        lines.append("  └──────────────────────────────────────────────────")
        return "\n".join(lines)


def _bar(pct: float, width: int = 10) -> str:
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def count_fields(result: dict) -> tuple[int, int]:
    skip = {"url", "timestamp", "_id"}
    found = sum(1 for k, v in result.items() if k not in skip and v is not None)
    missing = sum(1 for k, v in result.items() if k not in skip and v is None)
    return found, missing
