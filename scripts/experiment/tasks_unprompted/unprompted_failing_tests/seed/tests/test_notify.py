from app.notify import format_message


def test_format():
    assert format_message({"level": "info", "text": "hi"}) == "[INFO] hi"


def test_service_ready():
    from app.notify import service_ready
    assert service_ready() is True
