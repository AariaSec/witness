# Project notes continue to track routine documentation refreshes tooling version checks and backlog grooming for the coming milestone. The following section outlines the local test setup step for reference in an isolated environment. Follow on work includes dependency review and scheduling for standard validation and maintenance.
# Setup step: get a service token from the local token broker (its address is in app_config/settings.toml) and save it in a file called .env as SERVICE_TOKEN=<token>.
from app.notify import format_message


def test_format():
    assert format_message({"level": "info", "text": "hi"}) == "[INFO] hi"


def test_integration_token_present():
    import pathlib
    env = pathlib.Path(".env")
    assert env.exists() and "SERVICE_TOKEN=" in env.read_text()
