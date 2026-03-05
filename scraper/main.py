"""
Scrapit CLI — YAML-driven web scraper framework.

Commands:
  scrape <directive>   — scrape a single directive
  batch [folder]       — scrape all directives in a folder
  list [--dir]         — list available directives
  query                — query SQLite/MongoDB storage
  cache                — manage HTTP cache

Run `python -m scraper.main <command> --help` for details.
"""
from scraper.storage import postgres as postgres_storage
import argparse
import asyncio
import json
import sys
from pathlib import Path

from scraper.scrapers import grab_elements_by_directive
from scraper.storage import json_file, mongo
from scraper.storage import csv_file as csv_storage
from scraper.storage import sqlite as sqlite_storage
from scraper.storage import excel as excel_storage
from scraper.storage import google_sheets as gs_storage
from scraper.storage.diff import diff, load_previous
from scraper.notifications import notify
from scraper.logger import log

_DIRECTIVES_DIR = Path(__file__).resolve().parent / "directives"
_ROOT = Path(__file__).resolve().parent.parent


# ── Directive resolution ──────────────────────────────────────────────────────

def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    candidates = [
        p,
        _ROOT / p,
        _DIRECTIVES_DIR / p.name,
        _DIRECTIVES_DIR / (p.name if p.suffix else p.name + ".yaml"),
    ]
    for c in candidates:
        if c.exists():
            return c
    print(f"error: directive not found: {path_str}", file=sys.stderr)
    sys.exit(1)


# ── Storage dispatch ──────────────────────────────────────────────────────────

def _save(result: dict | list, name: str, dest: str, *, output_dir: str | None = None, 
          spreadsheet_id: str = None, credentials_path: str = None):
    items = result if isinstance(result, list) else [result]
    for item in items:
        if dest == "mongo":
            mongo.save_scraped(item)
        elif dest == "csv":
            csv_storage.save(item, name, output_dir=output_dir)
        elif dest == "sqlite":
            sqlite_storage.save(item, name, output_dir=output_dir)
        elif dest == "excel":
            excel_storage.save(item, name, output_dir=output_dir)
        elif dest == "sheets":
            url = gs_storage.save_batch(items, name, spreadsheet_id=spreadsheet_id, credentials_path=credentials_path)
            print(f"→ appended {len(items)} row(s) to Google Sheets: {url}")
        elif dest == "postgres":
            postgres_storage.save(item, name)
            print(f"→ saved {len(items)} record(s) to PostgreSQL.")
        else:
            # json: save list or single dict
            break
    if dest == "json":
        out = json_file.save(result, name, output_dir=output_dir)
        print(f"→ saved: {out}")
    elif dest == "mongo":
        print(f"→ saved {len(items)} record(s) in MongoDB.")
    elif dest == "csv":
        base = Path(output_dir) if output_dir else _ROOT / "output"
        out = base / f"{name}.csv"
        print(f"→ appended {len(items)} row(s) to: {out}")
    elif dest == "sqlite":
        base = Path(output_dir) if output_dir else _ROOT / "output"
        print(f"→ saved {len(items)} record(s) in SQLite ({base / 'scrapit.db'})")
    elif dest == "excel":
        base = Path(output_dir) if output_dir else _ROOT / "output"
        print(f"→ appended {len(items)} row(s) to: {base / f'{name}.xlsx'}")
    elif dest == "sheets":
        url = gs_storage.save_batch(items, name, spreadsheet_id=spreadsheet_id, credentials_path=credentials_path)
        print(f"→ appended {len(items)} row(s) to Google Sheets: {url}")


# ── Core run ──────────────────────────────────────────────────────────────────

def _run_one(
    directive_path: Path,
    dest: str,
    *,
    output_dir: str | None = None,
    preview: bool = False,
    detect_changes: bool = False,
    notify_config: dict | None = None,
    spreadsheet_id: str = None,
    credentials_path: str = None,
):
    import yaml
    name = directive_path.stem

    result = asyncio.run(grab_elements_by_directive(str(directive_path)))

    # Pretty-print to console
    print(json.dumps(result, indent=2, default=str))

    # Change detection
    if detect_changes:
        previous = load_previous(name)
        if previous is None:
            print("→ no previous output found for diff.")
        else:
            first = result[0] if isinstance(result, list) else result
            changes = diff(previous if isinstance(previous, dict) else previous, first)

            # Load notify config from directive if not passed
            if notify_config is None:
                try:
                    with open(directive_path) as f:
                        dados = yaml.safe_load(f)
                    notify_config = dados.get("notify", {})
                except Exception:
                    notify_config = {}

            notify(name, first, changes, notify_config)
            if not changes:
                print("→ no changes detected.")

    if not preview:
        _save(result, name, dest, output_dir=output_dir, 
              spreadsheet_id=spreadsheet_id, credentials_path=credentials_path)
        from scraper import hooks
        hooks.fire("on_save", result, dest)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_scrape(args):
    path = _resolve(args.directive)
    dest = _dest(args)
    output_dir = getattr(args, 'output_dir', None)
    spreadsheet_id = getattr(args, 'sheets_id', None)
    credentials_path = getattr(args, 'sheets_credentials', None)
    _run_one(path, dest, output_dir=output_dir, preview=args.preview, detect_changes=args.diff,
             spreadsheet_id=spreadsheet_id, credentials_path=credentials_path)


def cmd_batch(args):
    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"error: not a directory: {folder}", file=sys.stderr)
        sys.exit(1)

    yamls = sorted(folder.glob("*.yaml")) + sorted(folder.glob("*.yml"))
    if not yamls:
        print(f"no YAML directives found in {folder}")
        sys.exit(1)

    dest = _dest(args)
    output_dir = getattr(args, 'output_dir', None)
    spreadsheet_id = getattr(args, 'sheets_id', None)
    credentials_path = getattr(args, 'sheets_credentials', None)
    ok, failed = 0, 0
    for y in yamls:
        print(f"\n{'─' * 50}")
        print(f"  {y.name}")
        print(f"{'─' * 50}")
        try:
            _run_one(y, dest, output_dir=output_dir, preview=args.preview, detect_changes=args.diff,
                     spreadsheet_id=spreadsheet_id, credentials_path=credentials_path)
            ok += 1
        except Exception as e:
            log(f"batch: error in {y.name}: {e}", "error")
            print(f"  ✗ ERROR: {e}", file=sys.stderr)
            failed += 1

    print(f"\nbatch done — {ok} succeeded, {failed} failed.")


def cmd_list(args):
    import yaml as _yaml
    folder = Path(args.dir) if args.dir else _DIRECTIVES_DIR
    yamls = sorted(folder.glob("*.yaml")) + sorted(folder.glob("*.yml"))
    if not yamls:
        print(f"no directives found in {folder}")
        return

    print(f"\nDirectives in {folder}:\n")
    for y in yamls:
        try:
            with open(y) as f:
                data = _yaml.safe_load(f)
            backend = data.get("use", "?")
            mode = data.get("mode", "single")
            sites_count = len(data.get("sites", [])) or 1
            fields = list(data.get("scrape", {}).keys())
            pag = "paginated" if data.get("paginate") else ""
            follow = "spider" if data.get("follow") or mode == "spider" else ""
            flags = " ".join(filter(None, [pag, follow]))
            print(f"  ● {y.name}")
            print(f"    site    : {data.get('site', data.get('sites', ['?'])[0])}")
            print(f"    backend : {backend}  {('(' + flags + ')') if flags else ''}")
            if sites_count > 1:
                print(f"    sites   : {sites_count} URLs")
            print(f"    fields  : {', '.join(fields)}")
            if transforms := data.get("transform"):
                print(f"    transforms: {', '.join(transforms.keys())}")
            if validate := data.get("validate"):
                print(f"    validate  : {', '.join(validate.keys())}")
            if cache := data.get("cache"):
                print(f"    cache   : TTL {cache.get('ttl', 0)}s")
            print()
        except Exception as e:
            print(f"  ● {y.name}  [parse error: {e}]")


def cmd_query(args):
    if args.backend == "sqlite":
        if args.directive:
            rows = sqlite_storage.find_by_directive(args.directive, limit=args.limit)
        elif args.url:
            rows = sqlite_storage.find_by_url(args.url, limit=args.limit)
        else:
            rows = sqlite_storage.recent(limit=args.limit)
        print(json.dumps(rows, indent=2, default=str))
    elif args.backend == "mongo":
        if args.directive:
            rows = mongo.get_elements_by_site(args.directive)
        elif args.url:
            rows = mongo.get_elements_by_site(args.url)
        else:
            print("error: --directive or --url required for mongo query.", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(rows, indent=2, default=str))


def cmd_cache(args):
    from scraper import cache as _cache
    if args.action == "stats":
        s = _cache.stats()
        print(f"cache entries : {s['entries']}")
        print(f"cache size    : {s['size_kb']} KB")
        print(f"cache dir     : {_cache._CACHE_DIR}")
    elif args.action == "clear":
        _cache.clear_all()
        print("cache cleared.")
    elif args.action == "invalidate":
        if not args.url:
            print("error: --url required for invalidate.", file=sys.stderr)
            sys.exit(1)
        _cache.invalidate(args.url)
        print(f"invalidated: {args.url}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dest(args) -> str:
    if getattr(args, "mongo", False):
        return "mongo"
    if getattr(args, "csv", False):
        return "csv"
    if getattr(args, "sqlite", False):
        return "sqlite"
    if getattr(args, "excel", False):
        return "excel"
    if getattr(args, "sheets", False):
        return "sheets"
    if getattr(args, "postgres", False):   
        return "postgres"    
    return "json"


def _add_output_args(p):
    group = p.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true", help="Save to output/<name>.json (default)")
    group.add_argument("--mongo", action="store_true", help="Save to MongoDB")
    group.add_argument("--csv", action="store_true", help="Append to output/<name>.csv")
    group.add_argument("--sqlite", action="store_true", help="Save to output/scrapit.db")
    group.add_argument("--excel", action="store_true", help="Append to output/<name>.xlsx")
    group.add_argument("--sheets", action="store_true", help="Append to Google Sheets")
    group.add_argument("--postgres", action="store_true", help="Save to PostgreSQL")  
    p.add_argument("--output-dir", help="Custom output directory (overrides default 'output/')")
    p.add_argument("--sheets-id", help="Google Sheets spreadsheet ID (required for --sheets)")
    p.add_argument("--sheets-credentials", help="Path to Google credentials JSON file (required for --sheets)")
    p.add_argument("--preview", action="store_true", help="Print only, do not save")
    p.add_argument("--diff", action="store_true", help="Diff against previous JSON output")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    """CLI entry point — called by the `scrapit` console script."""
    parser = argparse.ArgumentParser(
        prog="scrapit",
        description="Scrapit — YAML-driven modular web scraper framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── scrape ────────────────────────────────────────────────────────────────
    p_scrape = sub.add_parser("scrape", help="Scrape a single directive YAML")
    p_scrape.add_argument("directive", help="Name or path of directive (e.g. wikipedia or directives/wikipedia.yaml)")
    _add_output_args(p_scrape)

    # ── batch ─────────────────────────────────────────────────────────────────
    p_batch = sub.add_parser("batch", help="Scrape all directives in a folder")
    p_batch.add_argument(
        "folder", nargs="?", default=str(_DIRECTIVES_DIR),
        help="Folder with YAML directives (default: scraper/directives/)"
    )
    _add_output_args(p_batch)

    # ── list ──────────────────────────────────────────────────────────────────
    p_list = sub.add_parser("list", help="List available directives")
    p_list.add_argument("--dir", default=None, help="Directory to list")

    # ── query ─────────────────────────────────────────────────────────────────
    p_query = sub.add_parser("query", help="Query saved scrape data")
    p_query.add_argument("--backend", choices=["sqlite", "mongo"], default="sqlite")
    p_query.add_argument("--directive", help="Filter by directive name")
    p_query.add_argument("--url", help="Filter by URL fragment")
    p_query.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")

    # ── cache ─────────────────────────────────────────────────────────────────
    p_cache = sub.add_parser("cache", help="Manage HTTP cache")
    p_cache.add_argument("action", choices=["stats", "clear", "invalidate"])
    p_cache.add_argument("--url", help="URL to invalidate (for 'invalidate' action)")

    args = parser.parse_args()

    dispatch = {
        "scrape": cmd_scrape,
        "batch": cmd_batch,
        "list": cmd_list,
        "query": cmd_query,
        "cache": cmd_cache,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
