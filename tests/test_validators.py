import pytest
from scraper.validators import validate, ValidationReport

def test_required_validation():
    rules = {"title": {"required": True}}
    
    # Present
    report = validate({"title": "Hello"}, rules)
    assert report.valid
    
    # Missing
    report = validate({}, rules)
    assert not report.valid
    assert len(report.errors) == 1
    assert "required" in str(report.errors[0])

def test_type_validation():
    rules = {"count": {"type": "int"}, "price": {"type": "float"}}
    
    # Correct
    report = validate({"count": 10, "price": 19.99}, rules)
    assert report.valid
    
    # Incorrect
    report = validate({"count": "10", "price": "19.99"}, rules)
    assert not report.valid
    assert len(report.errors) == 2

def test_numeric_range_validation():
    rules = {"score": {"min": 0, "max": 100}}
    
    # Valid
    assert validate({"score": 50}, rules).valid
    assert validate({"score": 0}, rules).valid
    assert validate({"score": 100}, rules).valid
    
    # Invalid
    report = validate({"score": -1}, rules)
    assert not report.valid
    assert "min" in str(report.errors[0])
    
    report = validate({"score": 101}, rules)
    assert not report.valid
    assert "max" in str(report.errors[0])

def test_length_validation():
    rules = {"tags": {"min_length": 2, "max_length": 4}}
    
    # Valid
    assert validate({"tags": ["a", "b"]}, rules).valid
    assert validate({"tags": "abc"}, rules).valid
    
    # Invalid
    assert not validate({"tags": ["a"]}, rules).valid
    assert not validate({"tags": "a"}, rules).valid
    assert not validate({"tags": [1, 2, 3, 4, 5]}, rules).valid

def test_regex_pattern_validation():
    rules = {"code": {"pattern": r"^SKU-\d+$"}}
    
    assert validate({"code": "SKU-123"}, rules).valid
    assert not validate({"code": "sku-123"}, rules).valid # case sensitive
    assert not validate({"code": "ABC-123"}, rules).valid

def test_enum_validation():
    rules = {"status": {"in": ["active", "pending"]}, "role": {"not_in": ["admin"]}}
    
    assert validate({"status": "active", "role": "user"}, rules).valid
    assert not validate({"status": "deleted"}, rules).valid
    assert not validate({"role": "admin"}, rules).valid

def test_composite_validation():
    rules = {
        "price": {
            "required": True,
            "type": "float",
            "min": 0.01
        }
    }
    
    assert validate({"price": 10.5}, rules).valid
    
    report = validate({"price": 0}, rules)
    assert not report.valid
    assert len(report.errors) == 1 # min failure (type int/float allows 0)
    
    report = validate({"price": -5.0}, rules)
    assert not report.valid

def test_validation_report_as_dict():
    rules = {"id": {"required": True}}
    report = validate({}, rules)
    
    data = report.as_dict()
    assert data["valid"] is False
    assert len(data["errors"]) == 1
    assert "[id]" in data["errors"][0]
