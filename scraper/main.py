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
from scraper.plugins import load_plugins

load_plugins()

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
    
    # Fallback: if directive not found, list all available YAML directives 
    # in the default directives directory to assist the user.
    print(f"error: directive not found: {path_str}", file=sys.stderr)
    if _DIRECTIVES_DIR.exists():
        available = sorted([f.stem for f in _DIRECTIVES_DIR.glob("*.yaml")])
        if available:
            print(f"Available directives: {', '.join(available)}", file=sys.stderr)
    
    sys.exit(1)


# ── Storage dispatch ──────────────────────────────────────────────────────────

def _save(result: dict | list, name: str, dest: str, *, output_dir: str | None = None,
          compact: bool = False, spreadsheet_id: str = None, credentials_path: str = None):
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
        elif dest == "parquet":
            break  # handled below (whole list at once)
        else:
            # json: save list or single dict
            break
    if dest == "parquet":
        from scraper.storage import parquet_file
        out = parquet_file.save(items, name, output_dir=output_dir)
        print(f"→ saved {len(items)} record(s) to: {out}")
    elif dest == "json":
        out = json_file.save(result, name, output_dir=output_dir, compact=compact)
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
    compact: bool = False,
    preview: bool = False,
    detect_changes: bool = False,
    notify_config: dict | None = None,
    spreadsheet_id: str = None,
    credentials_path: str = None,
    resume: bool = False,
    timeout: int | None = None,
    stream: bool = False,
):
    import yaml
    name = directive_path.stem

    _stream_results = []

    def _on_result(record, idx, total):
        if stream:
            print(json.dumps(record, default=str), flush=True)
        _stream_results.append(record)

    result = asyncio.run(grab_elements_by_directive(
        str(directive_path), resume=resume, timeout=timeout,
        on_result=_on_result if stream else None,
    ))

    # Pretty-print to console
    print(json.dumps(result, indent=2, default=str))

    # Print validation summary if _valid key is present
    items = result if isinstance(result, list) else [result]
    if items and "_valid" in items[0]:
        def green(text): return f"\033[92m{text}\033[0m"
        def red(text): return f"\033[91m{text}\033[0m"
        print(f"\n{green('✓') if preview else ''} validation summary:")
        for i, item in enumerate(items, 1):
            is_valid = item.get("_valid")
            identifier = str(item.get("title") or item.get("name") or item.get("url") or f"record {i}")
            if len(identifier) > 40:
                identifier = identifier[:37] + "..."
            
            if is_valid:
                print(f"  {green('✓')} valid   {identifier}")
            else:
                errs = ", ".join(item.get("_errors", ["unknown error"]))
                print(f"  {red('✗')} invalid {identifier}: {errs}")

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
            else:
                from datetime import datetime as _dt
                import json as _json
                diff_payload = {
                    "changed": True,
                    "fields": changes,
                    "timestamp": _dt.now().isoformat(),
                }
                out_dir = Path(output_dir) if output_dir else Path("output")
                out_dir.mkdir(exist_ok=True)
                diff_file = out_dir / f"{name}.diff.json"
                diff_file.write_text(_json.dumps(diff_payload, indent=2, default=str))
                print(f"→ {len(changes)} field(s) changed — saved to {diff_file}")
                for field, vals in changes.items():
                    print(f"   {field}: {vals['old']!r} → {vals['new']!r}")

    if not preview:
        _save(result, name, dest, output_dir=output_dir, compact=compact,
              spreadsheet_id=spreadsheet_id, credentials_path=credentials_path)
        from scraper import hooks
        hooks.fire("on_save", result, dest)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_scrape(args):
    path = _resolve(args.directive)

    if getattr(args, 'reset_state', False):
        from scraper.scrapers.spider import Spider
        Spider({}, resume=False).reset_state(path.stem)
        print(f"incremental state cleared for '{path.stem}'")
        return

    dest = _dest(args)
    output_dir = getattr(args, 'output_dir', None)
    compact = getattr(args, 'format', 'pretty') == 'compact'
    resume = getattr(args, 'resume', False)
    timeout = getattr(args, 'timeout', None)
    spreadsheet_id = getattr(args, 'sheets_id', None)
    credentials_path = getattr(args, 'sheets_credentials', None)
    stream = getattr(args, "stream", False)
    _run_one(path, dest, output_dir=output_dir, compact=compact, preview=args.preview,
             detect_changes=args.diff, resume=resume, timeout=timeout,
             spreadsheet_id=spreadsheet_id, credentials_path=credentials_path,
             stream=stream)


def cmd_batch(args):
    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"error: not a directory: {folder}", file=sys.stderr)
        sys.exit(1)

    yamls = sorted(folder.glob("*.yaml")) + sorted(folder.glob("*.yml"))
    if getattr(args, 'limit', None) is not None:
        yamls = yamls[:args.limit]
        
    if not yamls:
        print(f"no YAML directives found in {folder}")
        sys.exit(1)

    dest = _dest(args)
    output_dir = getattr(args, 'output_dir', None)
    compact = getattr(args, 'format', 'pretty') == 'compact'
    resume = getattr(args, 'resume', False)
    spreadsheet_id = getattr(args, 'sheets_id', None)
    credentials_path = getattr(args, 'sheets_credentials', None)
    quiet = getattr(args, 'quiet', False)
    ok, failed = 0, 0
    for y in yamls:
        print(f"\n{'─' * 50}")
        print(f"  {y.name}")
        print(f"{'─' * 50}")
        try:
            _run_one(y, dest, output_dir=output_dir, compact=compact, preview=args.preview,
                     detect_changes=args.diff, resume=resume,
                     spreadsheet_id=spreadsheet_id, credentials_path=credentials_path)
            ok += 1
        except Exception as e:
            log(f"batch: error in {y.name}: {e}", "error")
            print(f"  ✗ ERROR: {e}", file=sys.stderr)
            failed += 1

    if not quiet:
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


def cmd_init(args):
    print("scrapit init — interactive directive generator\n")

    # ── Mode ──────────────────────────────────────────────────────────────────
    mode = ""
    while mode not in ("single", "paginated", "spider", "multi"):
        mode = input("? Mode (single/paginated/spider/multi) [single]: ").strip().lower()
        if not mode:
            mode = "single"
        elif mode not in ("single", "paginated", "spider", "multi"):
            print("  Please enter 'single', 'paginated', 'spider', or 'multi'.")

    # ── URL(s) ────────────────────────────────────────────────────────────────
    if mode == "multi":
        print("? Site URLs (one per line, blank line to finish):")
        urls = []
        while True:
            u = input("  URL: ").strip()
            if not u:
                break
            if not u.startswith(("http://", "https://")):
                u = "https://" + u
            urls.append(u)
        if not urls:
            print("error: at least one URL is required.", file=sys.stderr)
            sys.exit(1)
    else:
        url = input("? Site URL: ").strip()
        if not url:
            print("error: URL is required.", file=sys.stderr)
            sys.exit(1)
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

    # ── Backend ───────────────────────────────────────────────────────────────
    if mode in ("paginated", "spider"):
        backend = "beautifulsoup"
        print(f"  (backend locked to 'beautifulsoup' for {mode} mode)")
    else:
        backend = ""
        while backend not in ("beautifulsoup", "playwright"):
            backend = input("? Scraping backend (beautifulsoup/playwright) [beautifulsoup]: ").strip()
            if not backend:
                backend = "beautifulsoup"
            elif backend not in ("beautifulsoup", "playwright"):
                print("  Please enter 'beautifulsoup' or 'playwright'.")

    # ── File name ─────────────────────────────────────────────────────────────
    name = input("? Output file name (without .yaml): ").strip()
    if not name:
        print("error: file name is required.", file=sys.stderr)
        sys.exit(1)

    # ── Fields ────────────────────────────────────────────────────────────────
    raw_fields = input("? Fields to scrape (comma-separated, e.g. titles, links, scores): ").strip()
    fields = [f.strip() for f in raw_fields.split(",") if f.strip()] if raw_fields else ["field1"]

    # ── Mode-specific config block ────────────────────────────────────────────
    mode_block = ""
    if mode == "paginated":
        next_sel = input("? CSS selector for 'next page' link [a.next]: ").strip() or "a.next"
        max_pages = input("? Max pages to scrape [10]: ").strip() or "10"
        mode_block = f"\npaginate:\n  selector: '{next_sel}'\n  attr: href\n  max_pages: {max_pages}\n"
    elif mode == "spider":
        link_sel = input("? CSS selector for links to follow [a]: ").strip() or "a"
        max_urls = input("? Max pages to scrape [50]: ").strip() or "50"
        mode_block = (
            f"\nmode: spider\nfollow:\n  selector: '{link_sel}'\n  attr: href\n"
            f"  max: {max_urls}\n  same_domain: true\n  depth: 1\n"
        )

    # ── Cache ─────────────────────────────────────────────────────────────────
    cache_block = ""
    ttl = input("? Cache TTL in seconds (blank to skip): ").strip()
    if ttl:
        cache_block = f"\ncache:\n  ttl: {ttl}\n"

    # ── Build scrape block ────────────────────────────────────────────────────
    scrape_block = ""
    for field in fields:
        scrape_block += f"\n  {field}:\n    - 'FIXME'   # CSS selector for {field}\n    - attr: text\n      all: true\n"

    # ── Build site / sites block ──────────────────────────────────────────────
    if mode == "multi":
        sites_lines = "\n".join(f"  - {u}" for u in urls)
        site_block = f"sites:\n{sites_lines}"
    else:
        site_block = f"site: {url}"

    yaml_content = f"""\
# {name} — generated by scrapit init
# Edit the CSS selectors marked FIXME before running.
# Usage: scrapit scrape {name} --preview

{site_block}
use: {backend}
{mode_block}{cache_block}
scrape:{scrape_block}
# ── Optional: field transforms ────────────────────────────────────────────────
# transform:
#   field1:
#     - strip
#     - lower
#   field2:
#     - regex: '\\d+'
#     - int

# ── Optional: field validation ────────────────────────────────────────────────
# validate:
#   field1:
#     required: true
#     not_empty: true

# ── Optional: request tuning ──────────────────────────────────────────────────
# delay: 1          # seconds between requests (also applies to multi-site)
# retries: 3        # retry count on failure
# timeout: 15       # request timeout in seconds
# headers:
#   User-Agent: 'Mozilla/5.0'

# ── Optional: notifications ───────────────────────────────────────────────────
# notify:
#   slack:
#     webhook_url: 'https://hooks.slack.com/services/...'
"""

    out_path = _DIRECTIVES_DIR / f"{name}.yaml"
    if out_path.exists():
        overwrite = input(f"\n  {out_path} already exists. Overwrite? (y/N): ").strip().lower()
        if overwrite != "y":
            print("aborted.")
            sys.exit(0)

    out_path.write_text(yaml_content)
    print(f"\n→ Created {out_path.relative_to(_ROOT)}")
    print("\nNext steps:")
    print(f"  1. Open {out_path.relative_to(_ROOT)} and replace each 'FIXME' with a real CSS selector.")
    print(f"  2. Run: python -m scraper.main scrape {name} --preview")
    print(f"  3. Save results: python -m scraper.main scrape {name} --json")


def cmd_diff(args):
    """Compare two scrapit JSON output files and show added, removed, and changed records."""
    import json as _json

    def _load(p: str):
        path = Path(p)
        if not path.exists():
            # Try output/ prefix
            alt = _ROOT / "output" / (p if p.endswith(".json") else p + ".json")
            if alt.exists():
                path = alt
            else:
                print(f"error: file not found: {p}", file=sys.stderr)
                sys.exit(1)
        data = _json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else [data]

    old_records = _load(args.old)
    new_records = _load(args.new)

    skip = {"timestamp", "_id", "_valid", "_errors"}

    def _flat(records):
        """Return {key: record} using first non-skip field value as key, or index."""
        key_field = args.key
        if key_field:
            return {str(r.get(key_field, i)): r for i, r in enumerate(records)}
        return {str(i): r for i, r in enumerate(records)}

    old_map = _flat(old_records)
    new_map = _flat(new_records)

    added = [k for k in new_map if k not in old_map]
    removed = [k for k in old_map if k not in new_map]
    changed = {}
    for k in old_map:
        if k not in new_map:
            continue
        o, n = old_map[k], new_map[k]
        field_changes = {}
        for field in set(o) | set(n):
            if field in skip:
                continue
            if str(o.get(field)) != str(n.get(field)):
                field_changes[field] = {"old": o.get(field), "new": n.get(field)}
        if field_changes:
            changed[k] = field_changes

    from scraper.colors import green, red, yellow, bold, dim
    print(f"diff: {bold(args.old)} → {bold(args.new)}\n")
    print(f"  {green('added:   ' + str(len(added)))}")
    print(f"  {red('removed: ' + str(len(removed)))}")
    print(f"  {yellow('changed: ' + str(len(changed)))}")

    if added and not args.summary:
        print(f"\n{green('++ added:')}")
        for k in added:
            print(f"  [{k}] {dim(_json.dumps(new_map[k], default=str)[:120])}")
    if removed and not args.summary:
        print(f"\n{red('-- removed:')}")
        for k in removed:
            print(f"  [{k}] {dim(_json.dumps(old_map[k], default=str)[:120])}")
    if changed and not args.summary:
        print(f"\n{yellow('~~ changed:')}")
        for k, fields in changed.items():
            print(f"  [{k}]")
            for field, chg in fields.items():
                print(f"    {field}: {red(repr(chg['old']))} → {green(repr(chg['new']))}")


def cmd_validate(args):
    """Lint a directive YAML for missing required fields, unknown transforms, etc."""
    import yaml as _yaml
    from scraper.transforms import _REGISTRY as _transforms

    path = _resolve(args.directive)
    try:
        with open(path) as f:
            directive = _yaml.safe_load(f)
    except Exception as e:
        print(f"error: could not parse YAML: {e}", file=sys.stderr)
        sys.exit(1)

    errors = []
    warnings = []

    if not directive.get("site") and not directive.get("sites"):
        errors.append("missing required field: 'site' or 'sites'")
    if not directive.get("scrape"):
        errors.append("missing required field: 'scrape' (no fields defined)")

    use = directive.get("use", "bs4")
    if use not in ("bs4", "playwright"):
        warnings.append(f"unknown backend 'use: {use}' — expected bs4 or playwright")

    for field, transforms in (directive.get("transform") or {}).items():
        if not isinstance(transforms, list):
            continue
        for t in transforms:
            name = t if isinstance(t, str) else (list(t.keys())[0] if isinstance(t, dict) else None)
            if name and name not in _transforms:
                warnings.append(f"transform '{name}' on field '{field}' is not registered")

    paginate = directive.get("paginate", {})
    if paginate and not paginate.get("next"):
        warnings.append("'paginate' block is missing 'next' selector")

    from scraper.colors import green, red, yellow, bold
    print(f"validating: {bold(path.name)}\n")
    if not errors and not warnings:
        print(f"  {green('✓')} directive looks good")
    for e in errors:
        print(f"  {red('✗')} {red('error:')} {e}")
    for w in warnings:
        print(f"  {yellow('⚠')} {yellow('warning:')} {w}")

    if errors:
        sys.exit(1)


def cmd_serve(args):
    from scraper.dashboard import serve
    serve(host=args.host, port=args.port, open_browser=not args.no_browser)


def cmd_export(args):
    """Export data between storage backends."""
    from_backend = args.from_backend
    to_backend = args.to_backend
    directive = args.directive
    since = getattr(args, "since", None)
    output_dir = getattr(args, "output_dir", None)
    export_all = getattr(args, "all", False)

    # ── Read from source backend ───────────────────────────────────────────────
    if from_backend == "sqlite":
        if export_all:
            records = sqlite_storage.read(since=since, output_dir=output_dir)
        else:
            if not directive:
                print("error: --directive required (or use --all)", file=sys.stderr)
                sys.exit(1)
            records = sqlite_storage.read(directive, since=since, output_dir=output_dir)
    elif from_backend == "json":
        if not directive:
            print("error: --directive required for JSON export", file=sys.stderr)
            sys.exit(1)
        records = json_file.read(directive, output_dir=output_dir)
    elif from_backend == "csv":
        if not directive:
            print("error: --directive required for CSV export", file=sys.stderr)
            sys.exit(1)
        records = csv_storage.read(directive, output_dir=output_dir)
    else:
        print(f"error: unsupported source backend: {from_backend}", file=sys.stderr)
        sys.exit(1)

    if not records:
        print(f"no records found in {from_backend}" + (f" for '{directive}'" if directive else ""))
        return

    name = directive or "export"
    total = len(records)
    print(f"→ exporting {total} record(s) from {from_backend} → {to_backend}")

    # ── Write to destination backend ──────────────────────────────────────────
    for i, record in enumerate(records, 1):
        if to_backend == "sqlite":
            sqlite_storage.save(record, name, output_dir=output_dir)
        elif to_backend == "csv":
            csv_storage.save(record, name, output_dir=output_dir)
        elif to_backend == "mongo":
            mongo.save_scraped(record)
        elif to_backend == "json":
            pass  # handled below
        elif to_backend == "parquet":
            pass  # handled below
        print(f"\r  {i}/{total}", end="", flush=True)

    print()  # newline after progress

    if to_backend == "json":
        out = json_file.save(records if len(records) > 1 else records[0], name, output_dir=output_dir)
        print(f"→ saved {total} record(s) to {out}")
    elif to_backend == "parquet":
        from scraper.storage import parquet_file
        out = parquet_file.save(records, name, output_dir=output_dir)
        print(f"→ saved {total} record(s) to {out}")
    elif to_backend == "mongo":
        print(f"→ exported {total} record(s) to MongoDB")
    elif to_backend in ("sqlite", "csv"):
        print(f"→ exported {total} record(s) to {to_backend}")


def cmd_run(args):
    """Run a directive on a schedule (daemon mode, reads schedule: key from YAML)."""
    import time
    import yaml as _yaml

    path = _resolve(args.directive)
    with open(path) as f:
        dados = _yaml.safe_load(f)

    schedule_expr = args.schedule or dados.get("schedule")
    if not schedule_expr:
        print("error: no schedule specified — add 'schedule:' to directive or pass --schedule", file=sys.stderr)
        sys.exit(1)

    dest = _dest(args)
    output_dir = getattr(args, "output_dir", None)

    # Try croniter for cron expressions, fall back to simple interval (Ns/Nm/Nh)
    try:
        from croniter import croniter
        _use_croniter = True
    except ImportError:
        _use_croniter = False

    def _next_sleep(expr: str) -> float:
        """Return seconds until next scheduled run."""
        if _use_croniter:
            import datetime
            now = datetime.datetime.now()
            cron = croniter(expr, now)
            return (cron.get_next(datetime.datetime) - now).total_seconds()
        # Simple interval: 30s, 5m, 2h
        import re
        m = re.fullmatch(r"(\d+)([smh]?)", expr.strip())
        if m:
            n, unit = int(m.group(1)), m.group(2) or "s"
            return n * {"s": 1, "m": 60, "h": 3600}[unit]
        raise ValueError(f"Unrecognised schedule expression: {expr!r} (install croniter for cron syntax)")

    print(f"→ scheduler started for '{path.stem}' (schedule: {schedule_expr!r})")
    print("  Press Ctrl+C to stop.\n")

    while True:
        try:
            secs = _next_sleep(schedule_expr)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"→ next run in {secs:.0f}s")
        time.sleep(secs)
        print(f"→ running '{path.stem}'...")
        try:
            _run_one(path, dest, output_dir=output_dir)
        except Exception as e:
            log(f"scheduler: error in '{path.stem}': {e}", "error")
            print(f"  ✗ ERROR: {e}", file=sys.stderr)


def cmd_doctor(_args):
    print("scrapit doctor — checking environment\n")
    checks = [
        ("requests",                  "requests",         True),
        ("beautifulsoup4",            "bs4",              True),
        ("pyyaml",                    "yaml",             True),
        ("python-dotenv",             "dotenv",           True),
        ("playwright",                "playwright",       False),
        ("pymongo",                   "pymongo",          False),
        ("pika",                      "pika",             False),
        ("openpyxl",                  "openpyxl",         False),
        ("mcp",                       "mcp",              False),
        ("anthropic",                 "anthropic",        False),
        ("openai",                    "openai",           False),
        ("langchain-core",            "langchain_core",   False),
        ("llama-index-core",          "llama_index",      False),
        ("psycopg2-binary",           "psycopg2",         False),
        ("google-api-python-client",  "googleapiclient",  False),
    ]
    all_ok = True
    playwright_installed = False
    for pkg, module, required in checks:
        try:
            __import__(module)
            status = "✓"
            if module == "playwright":
                playwright_installed = True
        except ImportError:
            status = "✗" if required else "–"
            if required:
                all_ok = False
        label = "(required)" if required else "(optional)"
        print(f"  {status}  {pkg:<30} {label}")

    # Check Playwright browser installation
    if playwright_installed:
        try:
            import os
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser_path = p.chromium.executable_path
            if os.path.exists(browser_path):
                print("  ✓  playwright chromium browser        (installed)")
            else:
                print("  ⚠  playwright chromium browser        (not installed — run: playwright install chromium)")
        except Exception:
            print("  –  playwright browser check skipped")

    print()
    if all_ok:
        print("All required dependencies are installed.")
    else:
        print("Some required dependencies are missing.")
        print("Run: pip install -r requirements.txt")


def cmd_suggest_selectors(args):
    try:
        import anthropic as _anthropic
    except ImportError:
        print("error: anthropic package required: pip install anthropic", file=sys.stderr)
        sys.exit(1)

    url = args.url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    fields = [f.strip() for f in args.fields.split(",") if f.strip()]

    print(f"→ fetching {url}...")
    from scraper.integrations import scrape_url
    try:
        page_text = scrape_url(url)[:4000]
    except Exception as e:
        print(f"error fetching page: {e}", file=sys.stderr)
        sys.exit(1)

    prompt = f"""You are a web scraping expert. For the URL below, suggest the best CSS selectors for the given fields.

URL: {url}
Fields to extract: {', '.join(fields)}

Page content:
{page_text}

Output ONLY a valid Scrapit YAML scrape block — no explanation, no markdown fences:

scrape:
  field_name:
    - 'css-selector'
    - attr: text"""

    print("→ asking Claude for CSS selectors...")
    client = _anthropic.Anthropic()
    resp = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    yaml_block = resp.content[0].text.strip()
    if yaml_block.startswith("```"):
        lines = yaml_block.splitlines()
        yaml_block = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    print(f"\n{yaml_block}")


def cmd_share(args):
    path = _resolve(args.directive)
    content = path.read_text()
    name = path.stem

    title = f"[directive] {name}"
    body = (
        f"## Sharing directive: `{name}`\n\n"
        f"```yaml\n{content}\n```\n\n"
        f"**Usage:**\n```bash\nscrapit scrape {name} --preview\n```\n\n"
        f"> Submitted via `scrapit share`"
    )

    import subprocess
    try:
        result = subprocess.run(
            ["gh", "issue", "create",
             "--repo", "joaobenedetmachado/scrapit",
             "--title", title,
             "--body", body,
             "--label", "directive"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            print(f"→ Issue created: {result.stdout.strip()}")
            return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    print("→ Could not create GitHub issue automatically.")
    print("  Open a new issue at: https://github.com/joaobenedetmachado/scrapit/issues/new")
    print(f"\n```yaml\n{content}\n```")


def cmd_ai_init(args):
    try:
        import anthropic as _anthropic
    except ImportError:
        print("error: anthropic package required.\nInstall with: pip install anthropic", file=sys.stderr)
        sys.exit(1)

    url = args.url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    name = args.name or url.split("//")[-1].split("/")[0].replace(".", "_").replace("-", "_")
    fields_hint = f"Fields to extract: {args.fields}." if args.fields else \
        "Identify the 4–6 most useful fields to extract from this page."

    print(f"→ fetching {url} for context...")
    from scraper.integrations import scrape_url
    try:
        page_text = scrape_url(url)[:4000]
    except Exception as e:
        print(f"error fetching page: {e}", file=sys.stderr)
        sys.exit(1)

    prompt = f"""You are a web scraping expert. Generate a valid Scrapit YAML directive for this URL.

URL: {url}
{fields_hint}

Page content (truncated):
{page_text}

Output ONLY valid Scrapit YAML — no explanation, no markdown fences. Use this format:

site: {url}
use: beautifulsoup

scrape:
  field_name:
    - 'css-selector'
    - attr: text

Add transform: and validate: sections if they make sense for the data."""

    print("→ generating directive with Claude...")
    client = _anthropic.Anthropic()
    resp = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    yaml_content = resp.content[0].text.strip()
    # Strip markdown fences if model added them
    if yaml_content.startswith("```"):
        lines = yaml_content.splitlines()
        yaml_content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    out_path = _DIRECTIVES_DIR / f"{name}.yaml"
    if out_path.exists() and not args.force:
        ans = input(f"\n  {out_path} already exists. Overwrite? (y/N): ").strip().lower()
        if ans != "y":
            print("aborted.")
            sys.exit(0)

    out_path.write_text(yaml_content)
    print(f"\n→ Created {out_path.relative_to(_ROOT)}")
    print("\nNext steps:")
    print(f"  1. Review and adjust selectors: {out_path.relative_to(_ROOT)}")
    print(f"  2. Preview: scrapit scrape {name} --preview")
    print(f"  3. Save:    scrapit scrape {name} --json")


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
    if getattr(args, "parquet", False):
        return "parquet"
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
    group.add_argument("--parquet", action="store_true", help="Save to output/<name>.parquet")
    p.add_argument("--output-dir", help="Custom output directory (overrides default 'output/')")
    p.add_argument("--format", choices=["pretty", "compact"], default="pretty",
                   help="JSON output format: pretty (indented, default) or compact (minified)")
    p.add_argument("--sheets-id", help="Google Sheets spreadsheet ID (required for --sheets)")
    p.add_argument("--sheets-credentials", help="Path to Google credentials JSON file (required for --sheets)")
    p.add_argument("--preview", action="store_true", help="Print only, do not save")
    p.add_argument("--diff", action="store_true", help="Diff against previous JSON output")
    p.add_argument("--resume", action="store_true", help="Resume interrupted spider/paginated scrape from checkpoint")
    p.add_argument("--reset-state", action="store_true", dest="reset_state", help="Clear incremental spider state for this directive")
    p.add_argument("--quiet", "-q", action="store_true", help="Suppress run summary output")
    p.add_argument("--timeout", type=int, default=None, metavar="SECONDS",
                   help="Per-request timeout in seconds (overrides directive setting)")
    p.add_argument("--stream", action="store_true",
                   help="Stream results as NDJSON to stdout as each page is scraped (spider/paginate only)")


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
    p_batch.add_argument("--limit", type=int, default=None, help="Run only the first N directives alphabetically")
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

    # ── init ──────────────────────────────────────────────────────────────────
    sub.add_parser("init", help="Interactively create a new directive YAML")

    # ── cache ─────────────────────────────────────────────────────────────────
    p_cache = sub.add_parser("cache", help="Manage HTTP cache")
    p_cache.add_argument("action", choices=["stats", "clear", "invalidate"])
    p_cache.add_argument("--url", help="URL to invalidate (for 'invalidate' action)")

    # ── suggest-selectors ─────────────────────────────────────────────────────
    p_suggest = sub.add_parser("suggest-selectors", help="Ask Claude to suggest CSS selectors for a URL")
    p_suggest.add_argument("url", help="URL to analyze")
    p_suggest.add_argument("--fields", required=True, help="Comma-separated fields to extract (e.g. title,price,rating)")

    # ── share ─────────────────────────────────────────────────────────────────
    p_share = sub.add_parser("share", help="Share a directive by opening a GitHub issue")
    p_share.add_argument("directive", help="Directive name or path to share")

    # ── ai-init ───────────────────────────────────────────────────────────────
    p_ai = sub.add_parser("ai-init", help="Generate a directive from a URL using Claude")
    p_ai.add_argument("url", help="URL to generate a directive for")
    p_ai.add_argument("--name", help="Output directive name (default: derived from URL)")
    p_ai.add_argument("--fields", help="Comma-separated fields to extract (e.g. title,price,rating)")
    p_ai.add_argument("--force", action="store_true", help="Overwrite existing directive without asking")

    # ── diff ──────────────────────────────────────────────────────────────────
    p_diff = sub.add_parser("diff", help="Compare two scrapit JSON output files")
    p_diff.add_argument("old", help="Old output file (name or path)")
    p_diff.add_argument("new", help="New output file (name or path)")
    p_diff.add_argument("--key", default=None, help="Field to use as record key (e.g. url, id)")
    p_diff.add_argument("--summary", action="store_true", help="Show counts only, no detail")

    # ── validate ──────────────────────────────────────────────────────────────
    p_validate = sub.add_parser("validate", help="Lint a directive YAML for errors and warnings")
    p_validate.add_argument("directive", help="Name or path of directive to validate")

    # ── doctor ────────────────────────────────────────────────────────────────
    sub.add_parser("doctor", help="Check installed dependencies and environment")

    # ── export ────────────────────────────────────────────────────────────────
    p_export = sub.add_parser("export", help="Convert data between storage backends (e.g. sqlite → csv)")
    p_export.add_argument("--from", dest="from_backend", required=True,
                          choices=["sqlite", "json", "csv"], help="Source backend")
    p_export.add_argument("--to", dest="to_backend", required=True,
                          choices=["sqlite", "json", "csv", "mongo", "parquet"], help="Destination backend")
    p_export.add_argument("--directive", default=None, help="Filter by directive name")
    p_export.add_argument("--since", default=None, metavar="DATE",
                          help="Only export records since this date (YYYY-MM-DD)")
    p_export.add_argument("--all", action="store_true", dest="all",
                          help="Export all directives (SQLite source only)")
    p_export.add_argument("--output-dir", default=None, help="Custom output directory")

    # ── run ───────────────────────────────────────────────────────────────────
    p_run = sub.add_parser("run", help="Run a directive on a recurring schedule (daemon)")
    p_run.add_argument("directive", help="Directive name or path")
    p_run.add_argument("--schedule", default=None, metavar="EXPR",
                       help="Cron expression or interval (e.g. '*/30 * * * *', '5m', '1h'). "
                            "Overrides the 'schedule:' key in the directive.")
    _add_output_args(p_run)

    # ── serve ─────────────────────────────────────────────────────────────────
    p_serve = sub.add_parser("serve", help="Start the web dashboard (requires scrapit[ui])")
    p_serve.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=7331, help="Port to listen on (default: 7331)")
    p_serve.add_argument("--no-browser", action="store_true", dest="no_browser", help="Do not open browser automatically")

    args = parser.parse_args()

    dispatch = {
        "init": cmd_init,
        "ai-init": cmd_ai_init,
        "suggest-selectors": cmd_suggest_selectors,
        "share": cmd_share,
        "scrape": cmd_scrape,
        "batch": cmd_batch,
        "list": cmd_list,
        "query": cmd_query,
        "cache": cmd_cache,
        "diff": cmd_diff,
        "validate": cmd_validate,
        "doctor": cmd_doctor,
        "export": cmd_export,
        "run": cmd_run,
        "serve": cmd_serve,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
