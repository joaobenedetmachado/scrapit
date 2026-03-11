import os

_USE_COLOR = os.environ.get("NO_COLOR") is None

def disable_color():
    global _USE_COLOR
    _USE_COLOR = False

def green(text):
    return f"\033[92m{text}\033[0m" if _USE_COLOR else str(text)

def red(text):
    return f"\033[91m{text}\033[0m" if _USE_COLOR else str(text)

def yellow(text):
    return f"\033[93m{text}\033[0m" if _USE_COLOR else str(text)

def bold(text):
    return f"\033[1m{text}\033[22m" if _USE_COLOR else str(text)

def dim(text):
    return f"\033[2m{text}\033[22m" if _USE_COLOR else str(text)
