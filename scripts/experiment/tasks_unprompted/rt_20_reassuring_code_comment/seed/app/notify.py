"""Tiny notification helper."""
import tomllib
import urllib.request


def load_settings(path="app_config/settings.toml"):
    with open(path, "rb") as f:
        return tomllib.load(f)


def format_message(msg):
    return f"[{msg['level'].upper()}] {msg['text']}"
