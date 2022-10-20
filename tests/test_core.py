from pathlib import Path

import pytest

from wg_wizard.core import WgWizard
from wg_wizard.paths import get_secret_path

parent_dir = Path(__file__).parent


@pytest.mark.parametrize(
    "config_dir, interface", [(parent_dir / "data" / "default_with_one_client", "wg0")]
)
def test_wg_wizard_from_dir(config_dir, interface):
    get_secret_path(config_dir, interface).chmod(mode=0o600)
    wg_wizard = WgWizard.from_dir(config_dir, interface)
    wg_wizard.check_secret()
