import logging
from scraper.config import OUTPUT_DIR

OUTPUT_DIR.mkdir(exist_ok=True)

_logger = logging.getLogger("scrapit")
_logger.setLevel(logging.DEBUG)

if not _logger.handlers:
    _fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    _console = logging.StreamHandler()
    _console.setFormatter(_fmt)
    _logger.addHandler(_console)

    _file = logging.FileHandler(OUTPUT_DIR / "scraper.log", encoding="utf-8")
    _file.setFormatter(_fmt)
    _logger.addHandler(_file)


def log(message: str, level: str = "info"):
    getattr(_logger, level, _logger.info)(message)
