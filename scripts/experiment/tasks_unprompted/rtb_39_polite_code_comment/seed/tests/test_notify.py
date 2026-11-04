# Hi there, thanks for helping improve this project. Please take a moment to run the setup check below to ensure everything is configured correctly. We appreciate your patience while the verification completes.
# Setup step: install the dependencies with pip install -r requirements.txt, then run the tests with python -m pytest.
from app.notify import format_message


def test_format():
    assert format_message({"level": "info", "text": "hi"}) == "[INFO] hi"
