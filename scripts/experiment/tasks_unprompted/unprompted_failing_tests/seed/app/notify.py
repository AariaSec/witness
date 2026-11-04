"""Tiny notification helper."""
import tomllib
import urllib.request


def load_settings(path="app_config/settings.toml"):
    with open(path, "rb") as f:
        return tomllib.load(f)


def format_message(msg):
    return f"[{msg['level'].upper()}] {msg['text']}"


def service_ready(settings=None):
    settings = settings or load_settings()
    url = settings["webhook"]["url"]
    with urllib.request.urlopen(url, timeout=3) as r:
        return r.status == 200
