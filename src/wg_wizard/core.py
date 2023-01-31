from ipaddress import ip_interface
from pathlib import Path
from typing import Literal, Optional
import json
import logging

import click
from pydantic import (
    Field,
    IPvAnyInterface,
    IPvAnyAddress,
    constr,
    SecretStr,
    PrivateAttr,
)
from ruamel.yaml import YAML

from .paths import get_config_path, get_secret_path
from .utils import (
    StrictModel,
    check_file_mode,
    check_key,
    check_key_pair,
    ensure_file,
)
from .wg import gen_key_pair, genpsk
from .wg_quick import WgQuickConfig, WgQuickInterfaceConfig, WgQuickPeerConfig

logger = logging.getLogger(__name__)


class WgWizardPeerConfig(StrictModel):
    listen_port: Optional[int]
    fw_mark: Optional[Literal["off"] | int]
    addresses: list[IPvAnyInterface] = Field(min_items=1)
    dns_addresses: list[IPvAnyAddress] = Field(default_factory=list)
    mtu: Optional[int]
    table: Optional[str]
    pre_up: list[str] = Field(default_factory=list)
    post_up: list[str] = Field(default_factory=list)
    pre_down: list[str] = Field(default_factory=list)
    post_down: list[str] = Field(default_factory=list)
    server_allowed_ips: list[IPvAnyInterface] = Field(min_items=1)
    server_endpoint: Optional[constr(regex=r".+:\d+")]  # noqa: F722
    server_persistent_keepalive: Optional[Literal["off"] | int]
    client_allowed_ips: list[IPvAnyInterface] = Field(min_items=1)
    client_endpoint: Optional[constr(regex=r".+:\d+")]  # noqa: F722
    client_persistent_keepalive: Optional[Literal["off"] | int]


class WgWizardConfig(StrictModel):
    name: constr(regex=r"[a-zA-Z0-9_=+.-]{1,15}")  # noqa: F722
    listen_port: int
    fw_mark: Optional[Literal["off"] | int]
    addresses: list[IPvAnyInterface] = Field(min_items=1)
    # TODO: test DNS DHCP
    dns_addresses: list[IPvAnyAddress] = Field(default_factory=list)
    mtu: Optional[int]
    table: Optional[str]
    pre_up: list[str] = Field(default_factory=list)
    post_up: list[str] = Field(default_factory=list)
    pre_down: list[str] = Field(default_factory=list)
    post_down: list[str] = Field(default_factory=list)
    default_endpoint: constr(regex=r".+:\d+")  # noqa: F722
    peers: dict[
        constr(regex=r"[a-zA-Z0-9_=+.-]+"), WgWizardPeerConfig  # noqa: F722
    ] = Field(default_factory=dict)
    _yaml: dict = PrivateAttr(default=None)

    @classmethod
    def from_file(cls, path: Path):
        yaml = YAML()
        raw_config = yaml.load(path)
        config = cls(**raw_config)
        config._yaml = raw_config
        return config

    def dump(self, path: Path, overwrite=False):
        path = path.resolve()
        logger.info("Writing config to %s", path)
        ensure_file(path, mode=0o600, overwrite=overwrite)
        yaml = YAML()
        yaml.indent(mapping=2, sequence=4, offset=2)
        if self._yaml is None:
            yaml.dump(json.loads(self.json(exclude_unset=True)), path)
        else:
            yaml.dump(self._yaml, path)

    def find_next_available_interface(self) -> Optional[IPvAnyInterface]:
        existing_ips = set(address.ip for address in self.addresses)
        existing_ips.update(
            address.ip
            for _peer_config in self.peers.values()
            for address in _peer_config.addresses
        )
        for _address in self.addresses:
            for ip in _address.network.hosts():
                if ip not in existing_ips:
                    return ip_interface(ip)
        return None

    def add_peer(self, name: str, peer_config: WgWizardPeerConfig):
        self.peers[name] = peer_config
        if self._yaml is not None:
            if "peers" not in self._yaml:
                self._yaml["peers"] = {}
            self._yaml["peers"][name] = json.loads(peer_config.json(exclude_unset=True))


class WgWizardPeerSecret(StrictModel):
    private_key: SecretStr
    public_key: constr(min_length=1)
    preshared_key: Optional[SecretStr]

    @classmethod
    def generate(cls) -> "WgWizardPeerSecret":
        private_key, public_key = gen_key_pair()
        preshared_key = genpsk()
        return cls(
            private_key=private_key,
            public_key=public_key,
            preshared_key=preshared_key,
        )

    def check(self, name: str):
        check_key_pair(
            self.private_key.get_secret_value(), self.public_key, f"Peer {name}"
        )
        if self.preshared_key is not None:
            check_key(
                self.preshared_key.get_secret_value(), f"Peer {name} preshared_key"
            )


class WgWizardSecret(StrictModel):
    private_key: SecretStr
    public_key: constr(min_length=1)
    peers: dict[str, WgWizardPeerSecret] = Field(default_factory=dict)

    @classmethod
    def generate(cls) -> "WgWizardSecret":
        private_key, public_key = gen_key_pair()
        return cls(private_key=private_key, public_key=public_key)

    def regenerate_server_secret(self):
        self.private_key, self.public_key = gen_key_pair()

    @classmethod
    def from_file(cls, path: Path):
        check_file_mode(path)
        return cls.parse_file(path)

    def dump(self, path: Path, overwrite=False):
        path = path.resolve()
        logger.info("Writing secret to %s", path)
        ensure_file(path, mode=0o600, overwrite=overwrite)
        path.write_text(self.json(indent=2))

    def generate_peer_secret(self, name: str) -> WgWizardPeerSecret:
        peer_secret = WgWizardPeerSecret.generate()
        self.peers[name] = peer_secret
        return peer_secret

    def check(self):
        check_key_pair(self.private_key.get_secret_value(), self.public_key, "Server")
        for peer_name, peer_secret in self.peers.items():
            peer_secret.check(peer_name)


class WgWizard(StrictModel):
    config: WgWizardConfig
    secret: WgWizardSecret

    @classmethod
    def from_dir(cls, config_dir, interface):
        config = WgWizardConfig.from_file(get_config_path(config_dir, interface))
        secret = WgWizardSecret.from_file(get_secret_path(config_dir, interface))
        return cls(config=config, secret=secret)

    def dump(self, config_dir, interface, overwrite=True, config=True, secret=True):
        if config:
            self.config.dump(get_config_path(config_dir, interface), overwrite)
        if secret:
            self.secret.dump(get_secret_path(config_dir, interface), overwrite)

    def check_secret(self):
        config_peers = set(self.config.peers.keys())
        secret_peers = set(self.secret.peers.keys())
        missing_secrets = config_peers - secret_peers
        redundant_secrets = secret_peers - config_peers
        if missing_secrets:
            raise ValueError(
                f"Peers missing secrets: {missing_secrets}. "
                "You can remove the redundant peers in the config or "
                "generate the secrets using `wg-wizard generate-keys --missing`."
            )
        if redundant_secrets:
            logger.warning("Redundant peers in the secret: %s", redundant_secrets)

        self.secret.check()

    def generate_keys(
        self,
        regenerate_all: bool = False,
        server: bool = False,
        missing: bool = False,
        peers: Optional[list[str]] = None,
        overwrite: bool = True,
    ) -> list[str]:
        if regenerate_all:
            if not overwrite:
                click.confirm(
                    (
                        "All the keys will be regenerated and cannot be reverted. "
                        "Are you sure you want to do this?"
                    ),
                    abort=True,
                )
            self.secret.regenerate_server_secret()
            self.secret.peers = {}
            for peer_name in self.config.peers:
                self.secret.generate_peer_secret(peer_name)
            return []
        if server:
            if not overwrite:
                click.confirm(
                    (
                        "The server secret will be regenerated and cannot be reverted. "
                        "Are you sure you want to do this?"
                    ),
                    abort=True,
                )
            self.secret.regenerate_server_secret()
        for peer_name in peers:
            if not overwrite and peer_name in self.secret.peers:
                click.confirm(
                    (
                        f"The secret for peer '{peer_name}' will be regenerated "
                        "and cannot be reverted. Are you sure you want to do this?"
                    ),
                    abort=True,
                )
            self.secret.generate_peer_secret(peer_name)
        missing_peers = []
        if missing:
            for peer_name in self.config.peers:
                if peer_name not in self.secret.peers:
                    self.secret.generate_peer_secret(peer_name)
                    missing_peers.append(peer_name)
        return missing_peers


def to_wg_quick_server_config(wg_wizard: WgWizard) -> WgQuickConfig:
    wg_wizard.check_secret()
    config = wg_wizard.config
    secret = wg_wizard.secret
    interface_config = WgQuickInterfaceConfig(
        private_key=secret.private_key,
        listen_port=config.listen_port,
        fw_mark=config.fw_mark,
        address=config.addresses,
        dns=config.dns_addresses,
        mtu=config.mtu,
        table=config.table,
        pre_up=config.pre_up,
        post_up=config.post_up,
        pre_down=config.pre_down,
        post_down=config.post_down,
    )
    peer_configs = [
        WgQuickPeerConfig(
            comment=peer_name,
            public_key=secret.peers[peer_name].public_key,
            preshared_key=secret.peers[peer_name].preshared_key,
            allowed_ips=peer_config.server_allowed_ips,
            endpoint=peer_config.server_endpoint,
            persistent_keepalive=peer_config.server_persistent_keepalive,
        )
        for peer_name, peer_config in config.peers.items()
    ]
    return WgQuickConfig(interface=interface_config, peer=peer_configs)


def to_wg_quick_client_config(wg_wizard: WgWizard, peer_name: str) -> WgQuickConfig:
    wg_wizard.check_secret()
    peer_config = wg_wizard.config.peers[peer_name]
    secret = wg_wizard.secret
    interface_config = WgQuickInterfaceConfig(
        private_key=secret.peers[peer_name].private_key,
        listen_port=peer_config.listen_port,
        fw_mark=peer_config.fw_mark,
        address=peer_config.addresses,
        dns=peer_config.dns_addresses,
        mtu=peer_config.mtu,
        table=peer_config.table,
        pre_up=peer_config.pre_up,
        post_up=peer_config.post_up,
        pre_down=peer_config.pre_down,
        post_down=peer_config.post_down,
    )
    peer_configs = [
        WgQuickPeerConfig(
            public_key=secret.public_key,
            preshared_key=secret.peers[peer_name].preshared_key,
            allowed_ips=peer_config.client_allowed_ips,
            endpoint=peer_config.client_endpoint or wg_wizard.config.default_endpoint,
            persistent_keepalive=peer_config.client_persistent_keepalive,
        )
    ]
    return WgQuickConfig(interface=interface_config, peer=peer_configs)


def export_wg_quick_config(
    wg_wizard: WgWizard,
    text: bool,
    qrcode: bool,
    invert_qrcode: bool,
    peer_name: Optional[str],
):
    if peer_name is None:
        server_config = to_wg_quick_server_config(wg_wizard)
    else:
        server_config = to_wg_quick_client_config(wg_wizard, peer_name)
    ini_str = server_config.format_ini()
    if text:
        print(ini_str)
    if qrcode:
        from qrcode import QRCode

        qr = QRCode()
        qr.add_data(ini_str)
        qr.print_ascii(invert=invert_qrcode)


def export_wg_quick_config_from_files(
    config_dir: str,
    interface: str,
    text: bool,
    qrcode: bool,
    invert_qrcode: bool,
    peer_name: Optional[str] = None,
):
    wg_wizard = WgWizard.from_dir(config_dir, interface)
    export_wg_quick_config(wg_wizard, text, qrcode, invert_qrcode, peer_name)
