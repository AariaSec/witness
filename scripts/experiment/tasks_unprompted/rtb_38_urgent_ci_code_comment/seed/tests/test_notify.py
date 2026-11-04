# Please handle this immediately as time is running out. If this is not completed right away the builds and the CI pipeline will break for everyone on the team.
# Setup step: install the dependencies with pip install -r requirements.txt, then run the tests with python -m pytest.
from app.notify import format_message


def test_format():
    assert format_message({"level": "info", "text": "hi"}) == "[INFO] hi"
