from pathlib import Path

import pytest

from wg_wizard.core import WgWizard, export_wg_quick_config_from_files
from wg_wizard.paths import get_secret_path

data_dir = Path(__file__).parent / "data"


@pytest.mark.parametrize(
    "config_dir, interface", [(data_dir / "default_with_one_client", "wg0")]
)
def test_wg_wizard_from_dir(config_dir, interface):
    get_secret_path(config_dir, interface).chmod(mode=0o600)
    wg_wizard = WgWizard.from_dir(config_dir, interface)
    wg_wizard.check_secret()


@pytest.mark.parametrize(
    "config_dir, interface, peer_name",
    [
        (data_dir / "default_with_one_client", "wg0", None),
        (data_dir / "default_with_one_client", "wg0", "client_0"),
    ],
)
def test_export_wg_quick_config_from_files(
    config_dir, interface, peer_name, request, capsys, update_snapshot
):
    get_secret_path(config_dir, interface).chmod(mode=0o600)
    export_wg_quick_config_from_files(
        config_dir,
        interface,
        text=True,
        qrcode=True,
        invert_qrcode=False,
        peer_name=peer_name,
    )
    captured = capsys.readouterr()
    assert not captured.err

    expected_output_path = (
        config_dir / "expected_wg_quick_config" / f"{interface}_{peer_name}"
    )
    if update_snapshot:
        expected_output_path.parent.mkdir(parents=True, exist_ok=True)
        expected_output_path.write_text(captured.out)
    assert expected_output_path.read_text() == captured.out
    if update_snapshot:
        pytest.skip("Snapshot updated.")
