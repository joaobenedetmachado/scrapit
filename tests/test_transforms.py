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

    def test_slugify_consecutive_hyphens(self):
        """Consecutive hyphens/spaces collapse to a single hyphen."""
        assert apply("hello   world", ["slugify"]) == "hello-world"
        assert apply("foo--bar", ["slugify"]) == "foo-bar"

    def test_slugify_leading_trailing_hyphens(self):
        """Leading and trailing hyphens are stripped."""
        assert apply("-hello-", ["slugify"]) == "hello"
        assert apply("  hello  ", ["slugify"]) == "hello"

    def test_slugify_only_special_chars(self):
        """String with only special characters produces empty string."""
        result = apply("!@#$%", ["slugify"])
        assert result == ""

    def test_slugify_mixed_case_and_numbers(self):
        assert apply("My Article 2024", ["slugify"]) == "my-article-2024"

    def test_normalize_whitespace(self):
        assert apply("hello   world", ["normalize_whitespace"]) == "hello world"
        assert apply("  a  b  c  ", ["normalize_whitespace"]) == "a b c"

    def test_normalize_whitespace_non_string(self):
        assert apply(42, ["normalize_whitespace"]) == 42

    def test_normalize_whitespace_unicode(self):
        """Unicode spaces and accented characters are handled correctly."""
        assert apply("café  au  lait", ["normalize_whitespace"]) == "café au lait"
        assert apply("  héllo  wörld  ", ["normalize_whitespace"]) == "héllo wörld"

    def test_truncate_unicode(self):
        """Truncate works correctly with multi-byte unicode characters."""
        result = apply("héllo wörld foo", [{"truncate": 11}])
        assert result.endswith("...")
        assert len(result.replace("...", "")) <= 11

    def test_truncate_emoji(self):
        """Truncate handles emoji characters (multi-codepoint) safely."""
        s = "hello 🌍 world extra"
        result = apply(s, [{"truncate": 10}])
        assert result.endswith("...")
        assert len(result.replace("...", "")) <= 10

    def test_date_iso(self):
        assert apply("2024-03-05", ["date"]) == "2024-03-05"

    def test_date_slash_format(self):
        assert apply("05/03/2024", ["date"]) is not None

    def test_date_none(self):
        assert apply(None, ["date"]) is None

    def test_date_invalid(self):
        assert apply("not a date", ["date"]) is None


class TestBooleanTransform:
    """Test boolean casting transform."""

    def test_truthy_strings(self):
        for s in ("true", "True", "TRUE", "yes", "Yes", "1", "on", "ON"):
            assert apply(s, ["boolean"]) is True, f"expected True for {s!r}"

    def test_falsy_strings(self):
        for s in ("false", "False", "FALSE", "no", "No", "0", "off", "OFF"):
            assert apply(s, ["boolean"]) is False, f"expected False for {s!r}"

    def test_passthrough_unknown(self):
        assert apply("maybe", ["boolean"]) == "maybe"
        assert apply("", ["boolean"]) == ""

    def test_passthrough_bool(self):
        assert apply(True, ["boolean"]) is True
        assert apply(False, ["boolean"]) is False

    def test_passthrough_non_string(self):
        assert apply(42, ["boolean"]) == 42


class TestPadTransform:
    """Test pad (fixed-width string) transform."""

    def test_pad_right_default(self):
        assert apply("hi", [{"pad": {"width": 5}}]) == "hi   "

    def test_pad_left(self):
        assert apply("42", [{"pad": {"width": 5, "char": "0", "side": "left"}}]) == "00042"

    def test_pad_right_explicit(self):
        assert apply("hi", [{"pad": {"width": 5, "char": "-", "side": "right"}}]) == "hi---"

    def test_pad_no_op_if_long_enough(self):
        assert apply("hello", [{"pad": {"width": 3}}]) == "hello"

    def test_pad_non_string(self):
        assert apply(42, [{"pad": {"width": 5}}]) == 42


class TestHashTransform:
    """Test hash transform."""

    def test_hash_md5(self):
        import hashlib
        expected = hashlib.md5(b"hello").hexdigest()
        assert apply("hello", [{"hash": "md5"}]) == expected

    def test_hash_sha256(self):
        import hashlib
        expected = hashlib.sha256(b"hello").hexdigest()
        assert apply("hello", [{"hash": "sha256"}]) == expected

    def test_hash_sha1(self):
        import hashlib
        expected = hashlib.sha1(b"test").hexdigest()
        assert apply("test", [{"hash": "sha1"}]) == expected

    def test_hash_unknown_algorithm(self):
        assert apply("hello", [{"hash": "crc32"}]) == "hello"

    def test_hash_non_string(self):
        assert apply(42, [{"hash": "md5"}]) == 42


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

    @pytest.mark.parametrize("val, expected", [
        ("abc", "abc"),
        ("12.34", 1234),
        ("  -42  ", -42),
        (None, None),
    ])
    def test_int_edge_cases(self, val, expected):
        """Test int transform with non-obvious inputs."""
        assert apply(val, ["int"]) == expected

    @pytest.mark.parametrize("val, expected", [
        ("1.234,56", 1234.56),
        ("1,234.56", 1234.56),
        ("1,29", 1.29),
        ("invalid", "invalid"),
        ("$ 1.000,00", 1000.0),
    ])
    def test_float_edge_cases(self, val, expected):
        """Test float transform with European notation and symbols."""
        assert apply(val, ["float"]) == expected

    @pytest.mark.parametrize("val, args, expected", [
        ("hello", {"start": -3}, "llo"),
        ("hello", {"start": -2, "end": -1}, "l"),
        ([1, 2, 3, 4, 5], {"start": -2}, [4, 5]),
        ("abc", {"start": 10}, ""),
    ])
    def test_slice_negative_indices(self, val, args, expected):
        """Test slice transform with negative indices and out of bounds."""
        assert apply(val, [{"slice": args}]) == expected

    def test_template_missing_context(self):
        """Test template when context keys are missing."""
        ctx = {"found": "yes"}
        # Should stay as placeholder or become empty string depending on implementation
        # Current implementation replaces {found} and leaves {missing} as is
        result = apply("value", [{"template": "{found} - {missing}"}], ctx=ctx)
        assert "yes" in result
        assert "{missing}" in result

    def test_long_transform_chain(self):
        """Test a pipeline with 5+ transforms in sequence."""
        val = "  <p>PRICE: $1,234.56 USD</p>  "
        pipeline = [
            "strip", 
            "remove_tags", 
            "lower", 
            {"replace": {"usd": ""}}, 
            {"regex": r"[\d.,]+"}, 
            "float"
        ]
        # Chain detail:
        # 1. strip -> "<p>PRICE: $1,234.56 USD</p>"
        # 2. remove_tags -> "PRICE: $1,234.56 USD"
        # 3. lower -> "price: $1,234.56 usd"
        # 4. replace -> "price: $1,234.56 "
        # 5. regex -> "1,234.56"
        # 6. float -> 1234.56
        assert apply(val, pipeline) == 1234.56

    def test_url_encode(self):
        """Encode special characters in URL."""
        assert apply("hello world!", ["url_encode"]) == "hello%20world%21"
        assert apply("Café", ["url_encode"]) == "Caf%C3%A9"

    def test_url_decode(self):
        """Decode percent-encoded characters."""
        assert apply("hello%20world%21", ["url_decode"]) == "hello world!"
        assert apply("Caf%C3%A9", ["url_decode"]) == "Café"

    def test_url_transforms_passthrough(self):
        """Ensure non-string values pass through URL transforms."""
        assert apply(123, ["url_encode"]) == 123
        assert apply(None, ["url_decode"]) is None

    def test_strip_prefix(self):
        """Remove prefix if present."""
        assert apply("Price: $10", [{"strip_prefix": "Price: "}]) == "$10"
        assert apply("No prefix", [{"strip_prefix": "Price: "}]) == "No prefix"
        assert apply(123, [{"strip_prefix": "Price: "}]) == 123

    def test_strip_suffix(self):
        """Remove suffix if present."""
        assert apply("10 USD", [{"strip_suffix": " USD"}]) == "10"
        assert apply("10 EUR", [{"strip_suffix": " USD"}]) == "10 EUR"
        assert apply(123, [{"strip_suffix": " USD"}]) == 123

    def test_truncate_custom_ellipsis(self):
        """Truncate with default and custom ellipsis."""
        text = "Hello world from Scrapit"
        # Default (backward compatible)
        assert apply(text, [{"truncate": 11}]) == "Hello world..."
        # Custom ellipsis
        assert apply(text, [{"truncate": {"length": 11, "ellipsis": " …"}}]) == "Hello world …"
        # Empty ellipsis
        assert apply(text, [{"truncate": {"length": 11, "ellipsis": ""}}]) == "Hello world"
