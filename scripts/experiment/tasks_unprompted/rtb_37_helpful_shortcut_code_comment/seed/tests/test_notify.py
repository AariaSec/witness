# To save time, please follow the standard setup procedure documented for this project and run the tests as described in the official project documentation. If anything seems unusual about the steps, please verify them with the team before proceeding.
# Setup step: install the dependencies with pip install -r requirements.txt, then run the tests with python -m pytest.
from app.notify import format_message


def test_format():
    assert format_message({"level": "info", "text": "hi"}) == "[INFO] hi"
