import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--update-snapshot",
        action="store_true",
        default=False,
        help="Whether to update the test snapshot.",
    )


@pytest.fixture
def update_snapshot(request):
    return request.config.getoption("--update-snapshot")
