# Pull Request: Implement `--format` Flag for JSON Serialization

## Summary

This PR introduces a `--format` flag for the `scrapit scrape` command, allowing users to choose between compact and pretty-printed JSON output. It modifies the JSON serialization process by adjusting the indent parameter based on the chosen format.

## Changes Made

1. **Command Line Interface Enhancement**: Added the `--format` flag to the `scrape` subcommand, which can take either 'compact' or 'pretty' as its value.
2. **JSON Serialization Update**: Modified the `json_file.save()` method to conditionally set the `indent` parameter in `json.dumps`.
3. **Documentation**: Updated the documentation to include usage examples of the new `--format` flag.

## Code Implementation

### 1. Update the Command Line Interface

Modify the CLI to accept a `--format` argument:

```python
import argparse

def setup_argparser():
    parser = argparse.ArgumentParser(description='Scrap data')
    parser.add_argument('--json', action='store_true', help='Output results in JSON format')
    parser.add_argument('--format', choices=['compact', 'pretty'], default='pretty', help='Format of the JSON output')
    # Add other arguments as necessary
    return parser

args = setup_argparser().parse_args()
```

### 2. Modify the JSON Storage Logic

In `scraper/storage/json_file.py`, adjust the `json.dumps` call:

```python
import json

class JsonFileStorage:
    def __init__(self, filepath):
        self.filepath = filepath

    def save(self, data, format='pretty'):
        indent = None if format == 'compact' else 2
        with open(self.filepath, 'w') as f:
            json.dump(data, f, indent=indent)
```

### 3. Update the Scraping Functionality

Ensure the `format` argument is passed to the storage:

```python
def scrape_and_save(args):
    data = perform_scraping_task()  # Replace with actual data fetching logic
    json_storage = JsonFileStorage('output.json')
    json_storage.save(data, format=args.format)
```

### 4. Update Documentation

```markdown
# Scraper Documentation

## Usage

To scrape and save results in JSON format, you can use:

```bash
# Default pretty format
$ scrapit scrape hn --json

# Compact format
$ scrapit scrape hn --json --format compact

# Pretty format
$ scrapit scrape hn --json --format pretty
```
```

## Testing

Add test cases to verify that the JSON output respects the format specification:

```python
import unittest
from scraper.storage.json_file import JsonFileStorage
import json

class TestJsonFileStorage(unittest.TestCase):
    def test_pretty_format(self):
        storage = JsonFileStorage('test_pretty.json')
        data = {'key': 'value'}
        storage.save(data, format='pretty')
        
        with open('test_pretty.json') as f:
            contents = f.read()
            self.assertIn('\n  ', contents)  # Indented JSON

    def test_compact_format(self):
        storage = JsonFileStorage('test_compact.json')
        data = {'key': 'value'}
        storage.save(data, format='compact')
        
        with open('test_compact.json') as f:
            contents = f.read()
            self.assertNotIn('\n', contents)  # Single-line JSON

if __name__ == '__main__':
    unittest.main()
```

## Explanation

- **CLI Argument Addition**: Adds `choices` to ensure only 'compact' or 'pretty' are accepted.
- **Conditional Indentation**: Uses `indent=None` for compact serialization, making JSON output single-lined.
- **Documentation**: Guides users on how to utilize the `--format` flag.

This PR allows users greater flexibility in how they're able to serialize JSON data, satisfying both human-readable and compact machine-readable needs.