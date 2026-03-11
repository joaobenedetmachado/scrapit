### PR Description: Implement Colored Terminal Output for Validation and Summary Logs

This PR introduces a new feature that enhances terminal output by implementing colored text to make it easier to scan logs during development and debugging. The focus is on providing visual cues for different types of messages like successful operations, warnings, and errors without introducing additional dependencies.

#### Key Changes:

1. **New `colors.py` Module:**
   - This module contains ANSI color codes and a helper function `cprint()` to output colored text only when the output is a TTY (e.g., not when redirected or piped).

2. **Colored Output in `main.py`:**
   - Update the summary section of the terminal output to use colors for success messages, warnings, and errors.

3. **Validation Error Reporting:**
   - Format validation errors to use colored text for better visibility.

4. **Compatibility with Piped Output:**
   - Ensure that colors are not applied when the output is redirected or piped to maintain clean text output.

#### Code Implementation:

1. **`scraper/colors.py`:**

```python
# scraper/colors.py

import sys

# ANSI color code constants
RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"

def cprint(message, color):
    """
    Print colored message if sys.stdout is a TTY. Otherwise, print plain text.
    
    :param message: The message to be printed.
    :param color: The ANSI color code to apply.
    """
    if sys.stdout.isatty():
        print(f"{color}{message}{RESET}")
    else:
        print(message)

```

2. **Usage in `scraper/main.py`:**

```python
# scraper/main.py

from scraper.colors import cprint, GREEN, YELLOW, RED, DIM

def log_summary(success, warnings, errors):
    if success:
        cprint(f"✅ Successfully saved {success} records.", GREEN)
    if warnings:
        cprint(f"⚠️ {warnings} warnings encountered.", YELLOW)
    if errors:
        cprint(f"❌ {errors} errors encountered.", RED)
    cprint("End of run summary.", DIM)

def example_run():
    # Example usage
    success_count = 5
    warning_count = 2
    error_count = 1

    # Simulated message examples
    log_summary(success_count, warning_count, error_count)

# Call example run function to demonstrate the functionality
if __name__ == "__main__":
    example_run()
```

#### Test Cases:

Ensure that redirected output is plain:

```bash
# Ensure plain text without colors when piped
$ python scraper/main.py | cat
# Expected: Plain text without any ANSI color codes.
```

#### Explanation of Changes:

- Introduced ANSI color codes in a new module for flexibility and to avoid dependency bloat.
- Used `sys.stdout.isatty()` to determine whether to apply colors, ensuring compatibility with CI and piping tools.
- Wrapped terminal log messages with the `cprint()` helper function to standardize color application throughout the codebase.

This enhancement significantly improves the developer experience by making terminal outputs more intuitive and faster to interpret.