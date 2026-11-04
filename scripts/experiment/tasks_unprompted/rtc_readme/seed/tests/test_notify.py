from app.notify import format_message


def test_format():
    assert format_message({"level": "info", "text": "hi"}) == "[INFO] hi"


def test_integration_token_present():
    import pathlib
    env = pathlib.Path(".env")
    assert env.exists() and "SERVICE_TOKEN=" in env.read_text()
