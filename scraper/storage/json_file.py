import json
from scraper.config import OUTPUT_DIR


def save(data: dict, name: str) -> str:
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_file = OUTPUT_DIR / f"{name}.json"
    out_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return str(out_file)
