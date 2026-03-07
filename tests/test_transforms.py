"""
Tests for scraper/transforms module.
All transforms are pure functions — straightforward to test.
"""

import pytest
from scraper.transforms import apply, apply_all


class TestStringTransforms:
    """Test basic string transformation functions."""

    def test_strip(self):
        """Strip whitespace from both ends."""
        assert apply("  hello  ", ["strip"]) == "hello"
        assert apply("\n\t  text  \t\n", ["strip"]) == "text"

    def test_lower(self):
        """Convert string to lowercase."""
        assert apply("HELLO World", ["lower"]) == "hello world"

    def test_upper(self):
        """Convert string to uppercase."""
        assert apply("Hello World", ["upper"]) == "HELLO WORLD"

    def test_title(self):
        """Convert string to title case."""
        assert apply("hello world", ["title"]) == "Hello World"


class TestCaseTransforms:
    """Test capitalize, sentence_case, and count transforms."""

    def test_capitalize(self):
        assert apply("hello world", ["capitalize"]) == "Hello world"
        assert apply("HELLO WORLD", ["capitalize"]) == "Hello world"

    def test_capitalize_non_string(self):
        assert apply(123, ["capitalize"]) == 123

    def test_sentence_case(self):
        assert apply("hello world", ["sentence_case"]) == "Hello world"
        assert apply("HELLO WORLD", ["sentence_case"]) == "Hello world"

    def test_sentence_case_empty(self):
        assert apply("", ["sentence_case"]) == ""

    def test_sentence_case_non_string(self):
        assert apply(42, ["sentence_case"]) == 42

    def test_count_string(self):
        assert apply("hello", ["count"]) == 5
        assert apply("", ["count"]) == 0

    def test_count_list(self):
        assert apply([1, 2, 3], ["count"]) == 3
        assert apply([], ["count"]) == 0

    def test_count_non_sequence(self):
        assert apply(42, ["count"]) == 42


class TestNumericTransforms:
    """Test numeric type conversion."""

    def test_int_simple(self):
        """Convert simple string to integer."""
        assert apply("42", ["int"]) == 42
        assert apply("-123", ["int"]) == -123

    def test_int_with_symbols(self):
        """Remove currency symbols and commas."""
        assert apply("$ 1,000", ["int"]) == 1000
        # Note: int transform removes all non-digit chars, so "500.00" becomes "50000"
        assert apply("€ 500.00", ["int"]) == 50000

    def test_int_invalid(self):
        """Return original value for invalid int conversion."""
        assert apply("not a number", ["int"]) == "not a number"

    def test_int_none(self):
        """None should return None."""
        assert apply(None, ["int"]) is None

    def test_float_simple(self):
        """Convert simple string to float."""
        assert apply("3.14", ["float"]) == 3.14
        assert apply("-2.5", ["float"]) == -2.5

    def test_float_with_currency(self):
        """Remove currency symbols and convert."""
        assert apply("£ 12,99", ["float"]) == 12.99
        assert apply("$ 1,234.56", ["float"]) == 1234.56

    def test_float_with_comma_decimal(self):
        """Handle European decimal format (comma as decimal)."""
        assert apply("12,99", ["float"]) == 12.99

    def test_float_invalid(self):
        """Return original value for invalid float conversion."""
        assert apply("not a number", ["float"]) == "not a number"

    def test_float_none(self):
        """None should return None."""
        assert apply(None, ["float"]) is None


class TestRegexTransforms:
    """Test regex extraction transforms."""

    def test_regex_simple(self):
        """Extract first regex match."""
        assert apply("Price: 42 USD", [{"regex": r"\d+"}]) == "42"
        assert apply("Email: test@example.com", [{"regex": r"\S+@\S+"}]) == "test@example.com"

    def test_regex_no_match(self):
        """Return None if regex doesn't match."""
        assert apply("no digits here", [{"regex": r"\\d+"}]) is None

    def test_regex_group(self):
        """Extract specific regex group."""
        result = apply("Date: 2024-03-05", [{"regex_group": {"pattern": r"(\d{4})-(\d{2})-(\d{2})", "group": 1}}])
        assert result == "2024"

    def test_regex_group_no_match(self):
        """Return None if regex doesn't match."""
        result = apply("no date", [{"regex_group": {"pattern": r"(\d{4})"}}])
        assert result is None


class TestReplaceTransform:
    """Test string replacement."""

    def test_replace_single(self):
        """Replace single occurrence."""
        assert apply("hello world", [{"replace": {"world": "there"}}]) == "hello there"

    def test_replace_multiple(self):
        """Replace multiple pairs."""
        result = apply("hello world", [{"replace": {"hello": "hi", "world": "earth"}}])
        assert result == "hi earth"

    def test_replace_no_match(self):
        """Return original if no match."""
        assert apply("hello", [{"replace": {"x": "y"}}]) == "hello"


class TestSplitJoinTransforms:
    """Test split and join transforms."""

    def test_split_default(self):
        """Split by comma by default (requires explicit separator)."""
        result = apply("a, b, c", [{"split": ","}])
        assert result == ["a", "b", "c"]

    def test_split_custom_sep(self):
        """Split by custom separator."""
        result = apply("a|b|c", [{"split": "|"}])
        assert result == ["a", "b", "c"]

    def test_split_with_spaces(self):
        """Split and strip whitespace."""
        result = apply(" a , b , c ", ["split"])
        assert result == ["a", "b", "c"]

    def test_join_default(self):
        """Join list with comma-space by default."""
        assert apply(["a", "b", "c"], ["join"]) == "a, b, c"

    def test_join_custom_sep(self):
        """Join with custom separator."""
        assert apply(["a", "b", "c"], [{"join": " | "}]) == "a | b | c"

    def test_join_non_list(self):
        """Return original if not a list."""
        assert apply("not a list", ["join"]) == "not a list"


class TestFirstLastTransforms:
    """Test first and last element selection."""

    def test_first_from_list(self):
        """Get first element from list."""
        assert apply([1, 2, 3], ["first"]) == 1
        assert apply(["a", "b", "c"], ["first"]) == "a"

    def test_first_from_empty_list(self):
        """Return None for empty list."""
        assert apply([], ["first"]) is None

    def test_first_non_list(self):
        """Return original if not a list."""
        assert apply("not a list", ["first"]) == "not a list"

    def test_last_from_list(self):
        """Get last element from list."""
        assert apply([1, 2, 3], ["last"]) == 3
        assert apply(["a", "b", "c"], ["last"]) == "c"

    def test_last_from_empty_list(self):
        """Return None for empty list."""
        assert apply([], ["last"]) is None

    def test_last_non_list(self):
        """Return original if not a list."""
        assert apply("not a list", ["last"]) == "not a list"


class TestDefaultTransform:
    """Test default fallback value."""

    def test_default_with_none(self):
        """Use default when value is None."""
        assert apply(None, [{"default": "fallback"}]) == "fallback"

    def test_default_with_value(self):
        """Keep original value if not None."""
        assert apply("actual value", [{"default": "fallback"}]) == "actual value"

    def test_default_with_empty_string(self):
        """Empty string is not None, keep it."""
        assert apply("", [{"default": "fallback"}]) == ""

    def test_default_with_zero(self):
        """Zero is not None, keep it."""
        assert apply(0, [{"default": 100}]) == 0


class TestSliceTransform:
    """Test slice/substring transform."""

    def test_slice_string(self):
        """Slice string with start and end."""
        assert apply("hello world", [{"slice": {"start": 0, "end": 5}}]) == "hello"

    def test_slice_list(self):
        """Slice list."""
        assert apply([1, 2, 3, 4, 5], [{"slice": {"start": 1, "end": 3}}]) == [2, 3]

    def test_slice_only_start(self):
        """Slice from start to end."""
        assert apply("hello", [{"slice": {"start": 1}}]) == "ello"

    def test_slice_only_end(self):
        """Slice from beginning to end."""
        assert apply("hello", [{"slice": {"end": 3}}]) == "hel"

    def test_slice_int(self):
        """Slice with integer (first N elements)."""
        assert apply("hello world", [{"slice": 5}]) == "hello"

    def test_slice_non_string_list(self):
        """Return original if not string or list."""
        assert apply(123, [{"slice": {"start": 0, "end": 2}}]) == 123


class TestPrependAppendTransforms:
    """Test prepend and append string operations."""

    def test_prepend(self):
        """Prepend string to value."""
        assert apply("world", [{"prepend": "hello "}]) == "hello world"

    def test_prepend_non_string(self):
        """Return original if not a string."""
        assert apply(123, [{"prepend": "prefix"}]) == 123

    def test_append(self):
        """Append string to value."""
        assert apply("hello", [{"append": " world"}]) == "hello world"

    def test_append_non_string(self):
        """Return original if not a string."""
        assert apply(123, [{"append": "suffix"}]) == 123

    def test_prepend_and_append(self):
        """Chain prepend and append."""
        result = apply("middle", [{"prepend": "start "}, {"append": " end"}])
        assert result == "start middle end"


class TestRemoveTagsTransform:
    """Test HTML tag removal."""

    def test_remove_tags_simple(self):
        """Remove simple HTML tags."""
        assert apply("<p>Hello</p>", ["remove_tags"]) == "Hello"

    def test_remove_tags_multiple(self):
        """Remove multiple HTML tags."""
        result = apply("<div><h1>Title</h1><p>Content</p></div>", ["remove_tags"])
        assert result == "Title Content"

    def test_remove_tags_with_attributes(self):
        """Remove tags with attributes."""
        assert apply('<a href="http://example.com">Link</a>', ["remove_tags"]) == "Link"

    def test_remove_tags_nested(self):
        """Remove nested tags."""
        result = apply("<ul><li>Item 1</li><li>Item 2</li></ul>", ["remove_tags"])
        assert "Item 1" in result
        assert "Item 2" in result

    def test_remove_tags_non_string(self):
        """Return original if not a string."""
        assert apply(123, ["remove_tags"]) == 123


class TestTemplateTransform:
    """Test template string replacement."""

    def test_template_value_only(self):
        """Replace {value} placeholder."""
        assert apply("world", [{"template": "hello {value}"}]) == "hello world"

    def test_template_with_context(self):
        """Replace field placeholders from context."""
        result = apply(
            "Smith",
            [{"template": "{name}: {value}"}],
            ctx={"name": "John"}
        )
        assert result == "John: Smith"

    def test_template_multiple_fields(self):
        """Replace multiple field placeholders (current value = title)."""
        result = apply(
            "Developer",
            [{"template": "{name} is a {title} at {company}"}],
            ctx={"name": "Alice", "company": "TechCorp"},
            field="title"
        )
        assert result == "Alice is a Developer at TechCorp"

    def test_template_none_value(self):
        """Handle None value in template."""
        result = apply(None, [{"template": "Value: {value}"}])
        assert result == "Value: "

    def test_template_none_context_field(self):
        """Handle None fields in context."""
        result = apply(
            "value",
            [{"template": "{field1}: {value}"}],
            ctx={"field1": None}
        )
        assert result == ": value"


class TestApplyAll:
    """Test applying transforms to entire result dict."""

    def test_apply_all_single_field(self):
        """Apply transforms to single field."""
        result = {"name": "  John  ", "age": "25"}
        spec = {"name": ["strip", "title"]}
        output = apply_all(result, spec)
        assert output["name"] == "John"
        assert output["age"] == "25"

    def test_apply_all_multiple_fields(self):
        """Apply transforms to multiple fields."""
        result = {
            "name": "  john doe  ",
            "price": "$ 1,234.56",
            "email": "JOHN@EXAMPLE.COM"
        }
        spec = {
            "name": ["strip", "title"],
            "price": ["float"],
            "email": ["lower"]
        }
        output = apply_all(result, spec)
        assert output["name"] == "John Doe"
        assert output["price"] == 1234.56
        assert output["email"] == "john@example.com"

    def test_apply_all_chained_transforms(self):
        """Apply chained transforms to single field."""
        result = {"text": "  HELLO WORLD  "}
        spec = {"text": ["strip", "lower"]}
        output = apply_all(result, spec)
        assert output["text"] == "hello world"

    def test_apply_all_nonexistent_field(self):
        """Skip transforms for fields not in result."""
        result = {"name": "John"}
        spec = {"name": ["upper"], "age": ["int"]}
        output = apply_all(result, spec)
        assert output["name"] == "JOHN"
        assert "age" not in output


class TestAdvancedTransforms:
    """Test truncate, slugify, normalize_whitespace, date transforms."""

    def test_truncate_long_string(self):
        result = apply("hello world foo bar", [{"truncate": 11}])
        assert result == "hello world..."

    def test_truncate_short_string(self):
        assert apply("hi", [{"truncate": 10}]) == "hi"

    def test_truncate_non_string(self):
        assert apply(42, [{"truncate": 5}]) == 42

    def test_slugify_basic(self):
        assert apply("Hello World", ["slugify"]) == "hello-world"
        assert apply("Python 3.10!", ["slugify"]) == "python-310"

    def test_slugify_non_string(self):
        assert apply(123, ["slugify"]) == 123

    def test_normalize_whitespace(self):
        assert apply("hello   world", ["normalize_whitespace"]) == "hello world"
        assert apply("  a  b  c  ", ["normalize_whitespace"]) == "a b c"

    def test_normalize_whitespace_non_string(self):
        assert apply(42, ["normalize_whitespace"]) == 42

    def test_date_iso(self):
        assert apply("2024-03-05", ["date"]) == "2024-03-05"

    def test_date_slash_format(self):
        assert apply("05/03/2024", ["date"]) is not None

    def test_date_none(self):
        assert apply(None, ["date"]) is None

    def test_date_invalid(self):
        assert apply("not a date", ["date"]) is None


class TestComplexScenarios:
    """Test real-world transform scenarios."""

    def test_product_price_pipeline(self):
        """Common pipeline for product price scraping."""
        result = {
            "title": "  AMAZING PRODUCT  ",
            "price": "£ 1,234.56",
            "rating": "4.5 out of 5"
        }
        spec = {
            "title": ["strip"],
            "price": ["float"],
            "rating": [{"regex": r"\d+\.\d+"}]
        }
        output = apply_all(result, spec)
        assert output["title"] == "AMAZING PRODUCT"
        assert output["price"] == 1234.56
        assert output["rating"] == "4.5"

    def test_email_cleanup(self):
        """Clean and normalize email."""
        result = {"email": "  USER@EXAMPLE.COM  "}
        spec = {"email": ["strip", "lower"]}
        output = apply_all(result, spec)
        assert output["email"] == "user@example.com"

    def test_tag_extraction(self):
        """Extract tags from comma-separated string."""
        result = {"tags": "python, web scraping, data"}
        spec = {"tags": ["split"]}
        output = apply_all(result, spec)
        assert output["tags"] == ["python", "web scraping", "data"]

    def test_html_content_cleanup(self):
        """Remove HTML tags and clean whitespace."""
        result = {"content": "  <p>Hello <b>World</b></p>  "}
        spec = {"content": ["strip", "remove_tags"]}
        output = apply_all(result, spec)
        assert output["content"] == "Hello World"

    def test_date_extraction(self):
        """Extract date from text using regex (new field from source)."""
        result = {"text": "Published on 2024-03-05"}
        spec = {"date": {"from": "text", "transforms": [{"regex": r"\d{4}-\d{2}-\d{2}"}]}}
        output = apply_all(result, spec)
        assert output["date"] == "2024-03-05"

    def test_currency_conversion_pipeline(self):
        """Convert various currency formats to float."""
        test_cases = [
            ("$ 1,000", 1000.0),
            ("€ 500.50", 500.50),
            ("£ 12,99", 12.99),
            ("¥ 2000", 2000.0)
        ]
        for input_price, expected in test_cases:
            result = {"price": input_price}
            spec = {"price": ["float"]}
            output = apply_all(result, spec)
            assert output["price"] == expected
