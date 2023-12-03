from pathlib import Path

import pytest
from click.testing import CliRunner

from wg_wizard.cli import add_peer, init
from wg_wizard.core import WgWizard

data_dir = Path(__file__).parent / "data"


@pytest.mark.parametrize(
    "expected_config_dir, interface", [(data_dir / "default_with_one_client", "wg0")]
)
def test_init_default_with_one_client(expected_config_dir, interface):
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            init,
            [
                "--interface",
                interface,
                "--default-endpoint",
                "example.com:51820",
                "--internet-interface-name",
                "eth0",
            ],
        )
        assert result.exit_code == 0
        result = runner.invoke(
            add_peer, ["--interface", interface, "--name", "client_0"]
        )
        assert result.exit_code == 0
        assert (
            Path(f"{interface}.yml").read_text()
            == Path(expected_config_dir, f"{interface}.yml").read_text()
        )
        WgWizard.from_dir("./", interface).check_secret()
