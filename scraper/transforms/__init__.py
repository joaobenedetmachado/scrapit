"""Transform pipeline — apply declarative transforms to scraped field values.

Supported transforms (use in directive under `transform:`):
  strip            — strip whitespace
  lower / upper / title — change case
  capitalize       — capitalize first character only
  sentence_case    — first char upper, rest lower
  int / float      — type cast
  count            — length of a string or list
  regex: pattern   — extract first regex match
  replace: {old: new} — string replace
  split: ","       — split into list
  first / last     — pick first/last element of a list
  default: value   — fallback if value is None
  slice: {start, end} — substring / sublist
  template: "..."  — f-string like: {value} {other_field}
  prepend: "str"   — prepend string
  append: "str"    — append string
  remove_tags      — strip HTML tags from string
  date             — parse date string to ISO format (YYYY-MM-DD)
  parse_date       — parse date with custom format
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

_REGISTRY: dict[str, callable] = {}


def _t(name):
    def deco(fn):
        _REGISTRY[name] = fn
        return fn
    return deco


@_t("strip")
def _strip(value, _, **__):
    return value.strip() if isinstance(value, str) else value


@_t("lower")
def _lower(value, _, **__):
    return value.lower() if isinstance(value, str) else value


@_t("upper")
def _upper(value, _, **__):
    return value.upper() if isinstance(value, str) else value


@_t("title")
def _title(value, _, **__):
    return value.title() if isinstance(value, str) else value


@_t("capitalize")
def _capitalize(value, _, **__):
    return value.capitalize() if isinstance(value, str) else value


@_t("sentence_case")
def _sentence_case(value, _, **__):
    if not isinstance(value, str) or not value:
        return value
    return value[0].upper() + value[1:].lower()


@_t("count")
def _count(value, _, **__):
    if isinstance(value, (str, list)):
        return len(value)
    return value


@_t("int")
def _int(value, _, **__):
    if value is None:
        return None
    try:
        return int(re.sub(r"[^\d\-]", "", str(value)))
    except ValueError:
        return value


def _normalize_number_string(s: str) -> str:
    """Remove currency/space, then normalize decimal: one comma or dot as decimal."""
    s = re.sub(r"[^\d.,\-]", "", s)
    if not s:
        return s
    # Both comma and dot: last one is decimal separator
    if "," in s and "." in s:
        last_comma, last_dot = s.rfind(","), s.rfind(".")
        if last_dot > last_comma:
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
        return s
    # Only comma: if ,XX (2 digits after) treat as decimal; else thousands
    if "," in s:
        if re.search(r",\d{2}$", s):
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    return s


@_t("float")
def _float(value, _, **__):
    if value is None:
        return None
    try:
        cleaned = _normalize_number_string(str(value))
        return float(cleaned)
    except ValueError:
        return value


@_t("regex")
def _regex(value, pattern, **__):
    if not isinstance(value, str):
        return value
    m = re.search(str(pattern), value, re.IGNORECASE | re.DOTALL)
    return m.group(0) if m else None


@_t("regex_group")
def _regex_group(value, args, **__):
    if not isinstance(value, str) or not isinstance(args, dict):
        return value
    pattern = args.get("pattern", "")
    group = args.get("group", 1)
    m = re.search(str(pattern), value, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    try:
        return m.group(group)
    except IndexError:
        return None


@_t("replace")
def _replace(value, args, **__):
    if not isinstance(value, str) or not isinstance(args, dict):
        return value
    for old, new in args.items():
        value = value.replace(str(old), str(new))
    return value


@_t("split")
def _split(value, sep=None, **__):
    if not isinstance(value, str):
        return value
    if sep is None:
        sep = ","
    return [v.strip() for v in value.split(str(sep)) if v.strip()]


@_t("join")
def _join(value, sep=None, **__):
    if not isinstance(value, list):
        return value
    if sep is None:
        sep = ", "
    return str(sep).join(str(v) for v in value)


@_t("first")
def _first(value, _, **__):
    if isinstance(value, list):
        return value[0] if value else None
    return value


@_t("last")
def _last(value, _, **__):
    if isinstance(value, list):
        return value[-1] if value else None
    return value


@_t("default")
def _default(value, fallback, **__):
    return fallback if value is None else value


@_t("slice")
def _slice(value, args, **__):
    if isinstance(args, dict):
        start = args.get("start", 0)
        end = args.get("end")
    elif isinstance(args, int):
        start, end = 0, args
    else:
        return value
    if isinstance(value, (str, list)):
        return value[start:end]
    return value


@_t("prepend")
def _prepend(value, prefix, **__):
    if isinstance(value, str):
        return str(prefix) + value
    return value


@_t("append")
def _append(value, suffix, **__):
    if isinstance(value, str):
        return value + str(suffix)
    return value


@_t("remove_tags")
def _remove_tags(value, _, **__):
    if not isinstance(value, str):
        return value
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", without_tags).strip()


@_t("normalize_whitespace")
def _normalize_whitespace(value, _, **__):
    if not isinstance(value, str):
        return value
    return re.sub(r"\s+", " ", value).strip()


@_t("truncate")
def _truncate(value, length, **__):
    if not isinstance(value, str):
        return value
    max_length = int(length)
    if len(value) <= max_length:
        return value
    truncated = value[:max_length]
    # Trim to last word boundary only if next char exists and is not space (cutting a word)
    if max_length < len(value) and value[max_length] not in (" ", ""):
        last_space = truncated.rfind(" ")
        if last_space > 0:
            truncated = truncated[:last_space]
    return truncated.rstrip() + "..."


@_t("slugify")
def _slugify(value, _, **__):
    if not isinstance(value, str):
        return value
    # Convert to lowercase
    value = value.lower()
    # Remove special characters (except alphanumeric, spaces, hyphens)
    value = re.sub(r"[^\w\s-]", "", value)
    # Replace spaces and underscores with hyphens
    value = re.sub(r"[\s_-]+", "-", value)
    # Strip leading/trailing hyphens
    return value.strip("-")


@_t("template")
def _template(value, pattern, ctx=None, field=None, **__):
    """Replace {value} with the field value and {field} with other fields."""
    if not isinstance(pattern, str):
        return value
    if ctx is not None and field is not None:
        ctx = {**ctx, field: value}
    elif ctx is None:
        ctx = {}
    result = str(pattern).replace("{value}", str(value) if value is not None else "")
    for k, v in ctx.items():
        result = result.replace(f"{{{k}}}", str(v) if v is not None else "")
    return result


# Common date formats to try when parsing
_COMMON_DATE_FORMATS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%m-%d-%Y",
    "%d.%m.%Y",
    "%Y.%m.%d",
    "%b %d, %Y",
    "%B %d, %Y",
    "%d %b %Y",
    "%d %B %Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%fZ",
]


def _try_parse_date(value: str, formats: list[str] | None = None):
    """Try to parse a date string using common formats."""
    if not isinstance(value, str) or not value.strip():
        return None
    
    value = value.strip()
    formats_to_try = formats or _COMMON_DATE_FORMATS
    
    for fmt in formats_to_try:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


@_t("date")
def _date(value, _, **__):
    """Convert date string to ISO format (YYYY-MM-DD).
    
    Tries common date formats automatically.
    Returns None if parsing fails.
    """
    if value is None:
        return None
    
    parsed = _try_parse_date(str(value))
    if parsed:
        return parsed.strftime("%Y-%m-%d")
    return None


@_t("parse_date")
def _parse_date(value, args, **__):
    """Parse date string with custom format and optionally output a specific format.
    
    Args (dict):
        input_format: str - the format of the input date string
        output_format: str - optional, format for output (default: ISO 8601 YYYY-MM-DD)
        formats: list - optional, list of formats to try (overrides input_format)
    
    Example:
        - parse_date: {input_format: "%d/%m/%Y"}
        - parse_date: {input_format: "%B %d, %Y", output_format: "%Y-%m-%d"}
    """
    if value is None:
        return None
    
    value = str(value).strip()
    
    # Determine formats to try
    formats = None
    output_fmt = "%Y-%m-%d"
    input_fmt = None
    
    if isinstance(args, dict):
        input_fmt = args.get("input_format")
        output_fmt = args.get("output_format", "%Y-%m-%d")
        formats = args.get("formats")
    
    # Try parsing
    parsed = None
    if formats and isinstance(formats, list):
        parsed = _try_parse_date(value, formats)
    elif formats and isinstance(formats, str):
        try:
            parsed = datetime.strptime(value, formats)
        except ValueError:
            pass
    elif input_fmt:
        try:
            parsed = datetime.strptime(value, input_fmt)
        except ValueError:
            parsed = _try_parse_date(value)
    else:
        parsed = _try_parse_date(value)
    
    if parsed:
        return parsed.strftime(output_fmt)
    return None


def apply(value: Any, transforms: list, ctx: dict | None = None, field: str | None = None) -> Any:
    """Apply a list of transforms to a single value."""
    for t in transforms:
        if isinstance(t, str):
            name, arg = t, None
        elif isinstance(t, dict):
            name, arg = next(iter(t.items()))
        else:
            continue
        fn = _REGISTRY.get(name)
        if fn:
            value = fn(value, arg, ctx=ctx, field=field)
    return value


def apply_all(result: dict, transform_spec: dict) -> dict:
    """Apply per-field transforms to an entire scraped result.
    If a spec value is dict with 'from' and 'transforms', create field from source.
    """
    out = dict(result)
    for field_name, spec in transform_spec.items():
        if isinstance(spec, dict) and "from" in spec:
            source = spec["from"]
            transforms = spec.get("transforms", [])
            if source in out:
                out[field_name] = apply(out[source], transforms, ctx=out, field=field_name)
        elif field_name in out:
            out[field_name] = apply(out[field_name], spec, ctx=out, field=field_name)
    return out
