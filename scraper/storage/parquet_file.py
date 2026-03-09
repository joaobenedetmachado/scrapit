"""
Parquet storage backend — saves scraped data as Apache Parquet.

Requires pyarrow: pip install scrapit[parquet]
"""
from pathlib import Path
from scraper.config import OUTPUT_DIR


def save(data: list[dict] | dict, name: str, output_dir: str | None = None) -> Path:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        raise ImportError(
            "pyarrow is required for Parquet output.\n"
            "Install with: pip install scrapit[parquet]"
        )

    rows = data if isinstance(data, list) else [data]
    out  = Path(output_dir) if output_dir else OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.parquet"

    table = pa.Table.from_pylist(rows)
    pq.write_table(table, str(path))
    return path
