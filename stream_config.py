"""
Your personal settings, shared by all the stream tools.

They live in config.json next to this file. That file is never uploaded to GitHub.
Anything still set to "INSERT_..." or left blank counts as not set.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")


def _is_set(value):
    if isinstance(value, str):
        return bool(value.strip()) and not value.strip().upper().startswith("INSERT_")
    return value is not None


def load():
    """Everything in config.json, or nothing if it's missing or broken."""
    try:
        with open(CONFIG_PATH, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        if os.path.exists(CONFIG_PATH):
            print(f"WARNING: couldn't read config.json, using defaults: {e}")
        return {}
    return data if isinstance(data, dict) else {}


CONFIG = load()


def get(key, default=None):
    value = CONFIG.get(key)
    return value if _is_set(value) else default


def folder(key, default_name):
    """A folder from config.json, or one with this name next to the scripts."""
    return os.path.expandvars(os.path.expanduser(get(key) or os.path.join(HERE, default_name)))


def folders(key):
    """A list of folders from config.json."""
    value = CONFIG.get(key)
    if not isinstance(value, list):
        return []
    return [os.path.expandvars(os.path.expanduser(v)) for v in value if _is_set(v)]
