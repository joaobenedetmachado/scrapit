"""
Transform pipeline — apply declarative transforms to scraped field values.

Supported transforms (use in directive under `transform:`):
  strip            — strip whitespace
  lower / upper    — change case
  int / float      — type cast
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
"""

import re
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


@_t("int")
def _int(value, _, **__):
    if value is None:
        return None
    try:
        return int(re.sub(r"[^\d\-]", "", str(value)))
    except ValueError:
        return value


@_t("float")
def _float(value, _, **__):
    if value is None:
        return None
    try:
        cleaned = re.sub(r"[^\d\.\,\-]", "", str(value)).replace(",", ".")
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
def _split(value, sep=",", **__):
    if not isinstance(value, str):
        return value
    return [v.strip() for v in value.split(str(sep)) if v.strip()]


@_t("join")
def _join(value, sep=", ", **__):
    if isinstance(value, list):
        return str(sep).join(str(v) for v in value)
    return value


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
    return re.sub(r"<[^>]+>", " ", value).strip()


@_t("template")
def _template(value, pattern, ctx=None, **__):
    """Replace {value} with the field value and {field} with other fields."""
    if not isinstance(pattern, str):
        return value
    result = str(pattern).replace("{value}", str(value) if value is not None else "")
    if ctx:
        for k, v in ctx.items():
            result = result.replace(f"{{{k}}}", str(v) if v is not None else "")
    return result


def apply(value: Any, transforms: list, ctx: dict | None = None) -> Any:
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
            value = fn(value, arg, ctx=ctx)
    return value


def apply_all(result: dict, transform_spec: dict) -> dict:
    """Apply per-field transforms to an entire scraped result."""
    out = dict(result)
    for field, transforms in transform_spec.items():
        if field in out:
            out[field] = apply(out[field], transforms, ctx=out)
    return out
