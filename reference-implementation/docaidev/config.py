"""Config lives in ~/.doc-aidev/config.json (override with DOC_AIDEV_HOME). Secrets are never stored here."""
import json
import os


def home():
    return os.path.expanduser(os.environ.get("DOC_AIDEV_HOME", "~/.doc-aidev"))


def path():
    return os.path.join(home(), "config.json")


def load():
    try:
        with open(path(), encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None


def save(cfg):
    os.makedirs(home(), exist_ok=True)
    with open(path(), "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
    return path()
