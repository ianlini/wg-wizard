from pathlib import Path

import pytest

from wg_wizard.core import WgWizard, export_wg_quick_config_from_files
from wg_wizard.paths import get_secret_path

parent_dir = Path(__file__).parent


@pytest.mark.parametrize(
    "config_dir, interface", [(parent_dir / "data" / "default_with_one_client", "wg0")]
)
def test_wg_wizard_from_dir(config_dir, interface):
    get_secret_path(config_dir, interface).chmod(mode=0o600)
    wg_wizard = WgWizard.from_dir(config_dir, interface)
    wg_wizard.check_secret()


@pytest.mark.parametrize(
    "config_dir, interface, peer_name",
    [
        (parent_dir / "data" / "default_with_one_client", "wg0", None),
        (parent_dir / "data" / "default_with_one_client", "wg0", "client_0"),
    ],
)
def test_export_wg_quick_config_from_files(config_dir, interface, peer_name):
    get_secret_path(config_dir, interface).chmod(mode=0o600)
    export_wg_quick_config_from_files(
        config_dir,
        interface,
        text=True,
        qrcode=True,
        invert_qrcode=False,
        peer_name=peer_name,
    )
