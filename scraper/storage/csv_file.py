import csv
from datetime import datetime
from scraper.config import OUTPUT_DIR


def save(data: dict, name: str) -> str:
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_file = OUTPUT_DIR / f"{name}.csv"
    file_exists = out_file.exists()

    flat = {k: str(v) for k, v in data.items()}

    with open(out_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=flat.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(flat)

    return str(out_file)
