"""
Validation engine — validate scraped field values against rules defined in the directive.

Supported rules (use in directive under `validate:`):
  required: true       — field must not be None
  type: str|int|float|list|bool — type check
  min: N               — minimum numeric value
  max: N               — maximum numeric value
  min_length: N        — minimum string/list length
  max_length: N        — maximum string/list length
  pattern: regex       — string must match regex
  in: [a, b, c]        — value must be one of the listed options
  not_empty: true      — string/list must not be empty
"""

import re
from dataclasses import dataclass, field


@dataclass
class ValidationError:
    field: str
    rule: str
    message: str

    def __str__(self):
        return f"[{self.field}] {self.rule}: {self.message}"


@dataclass
class ValidationReport:
    errors: list[ValidationError] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors

    def add(self, field_name: str, rule: str, message: str):
        self.errors.append(ValidationError(field_name, rule, message))

    def __str__(self):
        if self.valid:
            return "valid"
        return "\n".join(str(e) for e in self.errors)

    def as_dict(self) -> dict:
        return {"valid": self.valid, "errors": [str(e) for e in self.errors]}


_TYPE_MAP = {
    "str": str,
    "int": int,
    "float": (int, float),
    "list": list,
    "bool": bool,
}


def validate(result: dict, rules: dict) -> ValidationReport:
    report = ValidationReport()

    for field_name, field_rules in rules.items():
        value = result.get(field_name)

        # required
        if field_rules.get("required") and value is None:
            report.add(field_name, "required", "value is required but missing or null")
            continue

        if value is None:
            continue

        # type
        expected_type = field_rules.get("type")
        if expected_type:
            t = _TYPE_MAP.get(expected_type)
            if t and not isinstance(value, t):
                report.add(
                    field_name, "type",
                    f"expected {expected_type}, got {type(value).__name__}"
                )

        # not_empty
        if field_rules.get("not_empty") and not value:
            report.add(field_name, "not_empty", "value must not be empty")

        # numeric bounds
        if isinstance(value, (int, float)):
            if "min" in field_rules and value < field_rules["min"]:
                report.add(field_name, "min", f"{value} < min({field_rules['min']})")
            if "max" in field_rules and value > field_rules["max"]:
                report.add(field_name, "max", f"{value} > max({field_rules['max']})")

        # string / list length
        if isinstance(value, (str, list)):
            length = len(value)
            if "min_length" in field_rules and length < field_rules["min_length"]:
                report.add(field_name, "min_length", f"length {length} < {field_rules['min_length']}")
            if "max_length" in field_rules and length > field_rules["max_length"]:
                report.add(field_name, "max_length", f"length {length} > {field_rules['max_length']}")

        # regex pattern (strings only)
        if isinstance(value, str) and "pattern" in field_rules:
            if not re.search(str(field_rules["pattern"]), value):
                report.add(field_name, "pattern", f"does not match pattern: {field_rules['pattern']}")

        # in (enum)
        if "in" in field_rules and value not in field_rules["in"]:
            report.add(field_name, "in", f"{value!r} not in allowed values: {field_rules['in']}")

    return report
