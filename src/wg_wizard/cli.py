from functools import partial
import logging

import click

logger = logging.getLogger(__name__)
option = partial(click.option, show_default=True)
interface_option = option(
    "--interface",
    "-i",
    prompt="Interface name for WireGuard",
    help="Interface name for WireGuard.",
    default="wg0",
)
config_dir_option = option(
    "--config-dir",
    "-c",
    help="The directory for the wg-wizard configs and secrets.",
    type=click.Path(),
    default=".",
)
invert_qrcode_option = option(
    "--invert-qrcode/--no-invert-qrcode",
    is_flag=True,
    default=True,
    help="Whether to invert the color of the QR Code.",
)


@click.group(context_settings={"max_content_width": 120})
@click.version_option()
def main():
    logging.basicConfig(
        level=logging.INFO, format="[%(asctime)s][%(levelname)s] %(name)s: %(message)s"
    )


@main.command()
@interface_option
@config_dir_option
@option(
    "--listen-port",
    "-p",
    prompt="Interface.ListenPort of the relay server",
    help="Interface.ListenPort of the relay server.",
    default=51820,
    type=int,
)
@option(
    "--addresses",
    "-a",
    prompt="Interface.Address of the relay server",
    help="Interface.Address of the relay server.",
    default="192.168.10.1/24",
)
@option(
    "--default-endpoint",
    "-e",
    prompt="The default endpoint in clients' Peer.Endpoint configs (e.g., example.com:51280)",
    help="""
        The default endpoint in clients' Peer.Endpoint configs (e.g., example.com:51280).
        If the port is not provided, it will be added automatically according to the listen_port.
        The endpoint can also be overridden in peer configs.
    """,
)
@option(
    "--internet-interface-name",
    default="",
    prompt=(
        "If you want to allow the clients to access the internet via the relay server, "
        "you must provide the interface name you want to forward the internet traffic to. "
        "It's usually eth0 or wlan0. You can check it by executing `ip addr`. "
        "If you provide an interface name {interface}, the following rules will be added:\n"
        "- iptables -A FORWARD -i %i -o {interface} -j ACCEPT\n"
        "- iptables -A FORWARD -i {interface} -o %i -j ACCEPT\n"
        "- iptables -t nat -A POSTROUTING -s {network} -o {interface} -j MASQUERADE\n"
        "Interface name for connecting to the internet"
    ),
    help="""
        Interface name for connecting to the internet.
        If you want to allow the clients to access the internet via the relay server,
        you must provide the interface name you want to forward the internet traffic to.
        It's usually eth0 or wlan0. You can check it by executing `ip addr`.
        If you provide an interface name {interface}, the following rules will be added:
        [`iptables -A FORWARD -i %i -o {interface} -j ACCEPT`,
        `iptables -A FORWARD -i {interface} -o %i -j ACCEPT`,
        `iptables -t nat -A POSTROUTING -s {network} -o {interface} -j MASQUERADE`].
    """,
)
@option(
    "--allow-intranet/--no-allow-intranet",
    is_flag=True,
    default=True,
    prompt=(
        "Do you want to allow the clients to connect with each other? "
        "If yes, a rule will be added: `iptables -A FORWARD -i %i -o %i -j ACCEPT`"
    ),
    help="""
        Whether to allow the clients to connect with each other.
        If yes, a rule will be added: `iptables -A FORWARD -i %i -o %i -j ACCEPT`.
    """,
)
@option(
    "--allow-all-server-ip/--no-allow-all-server-ip",
    is_flag=True,
    default=False,
    prompt=(
        "Do you want to allow the clients to connect to any IPs on the relay server? "
        "If no, only the IP of the WireGuard interface can be connected, "
        "that is, the following rules will be added:\n"
        "- iptables -A INPUT -d {wg_server_interface_ip} -i %i -j ACCEPT\n"
        "- iptables -A INPUT -i %i -j DROP\n"
    ),
    help="""
        Wether to allow the clients to connect to any IPs on the relay server.
        If no, only the IP of the WireGuard interface can be connected,
        that is, the following rules will be added:
        [`iptables -A INPUT -d {wg_server_interface_ip} -i %i -j ACCEPT`,
        `iptables -A INPUT -i %i -j DROP`].
    """,
)
@option(
    "--overwrite/--no-overwrite",
    help="Whether to overwrite the config and secret files without confirmation.",
    is_flag=True,
)
def init(
    interface,
    config_dir,
    listen_port,
    addresses,
    default_endpoint,
    internet_interface_name,
    allow_intranet,
    allow_all_server_ip,
    overwrite,
):
    """Initialize a new wg-wizard config."""
    from .core import WgWizard, WgWizardConfig, WgWizardSecret
    from .utils import get_iptables_commands

    if ":" not in default_endpoint:
        default_endpoint += f":{listen_port}"
    addresses = [ip.strip() for ip in addresses.split(",")]

    post_up, pre_down = get_iptables_commands(
        internet_interface_name,
        allow_intranet,
        allow_all_server_ip,
        wg_server_interfaces=addresses,
    )
    config = WgWizardConfig(
        name=interface,
        listen_port=listen_port,
        addresses=addresses,
        post_up=post_up,
        pre_down=pre_down,
        default_endpoint=default_endpoint,
        peers={},
    )
    secret = WgWizardSecret.generate()
    WgWizard(config=config, secret=secret).dump(config_dir, interface, overwrite)


@main.command()
@interface_option
@config_dir_option
@option(
    "--name",
    "-n",
    prompt="Name of the peer",
    help="Name of the peer.",
)
@option(
    "--addresses",
    "-a",
    help="Interface.Address of the client.",
)
@option(
    "--client-allowed-ips",
    help="Peer.AllowedIPs of the client.",
)
@option(
    "--client-persistent-keepalive",
    prompt="Peer.PersistentKeepalive of the client",
    help="Peer.PersistentKeepalive of the client.",
    default=25,
)
@invert_qrcode_option
def add_peer(
    interface,
    config_dir,
    name,
    addresses,
    client_allowed_ips,
    client_persistent_keepalive,
    invert_qrcode,
):
    """Add a new client to a wg-wizard config."""
    from .core import WgWizard, WgWizardPeerConfig, export_wg_quick_config

    wg_wizard = WgWizard.from_dir(config_dir, interface)
    config = wg_wizard.config

    # check name
    if name in config.peers:
        raise ValueError("Peer name must be unique.")

    # get default addresses and client_allowed_ips and then ask the user
    if addresses is None:
        addresses = click.prompt(
            "Interface.Address of the client",
            default=str(config.find_next_available_interface()),
        )
    addresses = [ip.strip() for ip in addresses.split(",")]
    if client_allowed_ips is None:
        client_allowed_ips = click.prompt(
            "Peer.AllowedIPs of the client", default="0.0.0.0/0, ::/0"
        )
    client_allowed_ips = [ip.strip() for ip in client_allowed_ips.split(",")]

    # add a peer to the config
    peer_config = WgWizardPeerConfig(
        addresses=addresses,
        server_allowed_ips=addresses,
        client_allowed_ips=client_allowed_ips,
        client_persistent_keepalive=client_persistent_keepalive,
    )
    config.add_peer(name, peer_config)

    # generate secret
    wg_wizard.secret.generate_peer_secret(name)
    wg_wizard.dump(config_dir, interface)

    logger.info("Client's wg-quick config QR Code:")
    export_wg_quick_config(
        wg_wizard, text=False, qrcode=True, invert_qrcode=invert_qrcode, peer_name=name
    )


@main.command()
@interface_option
@config_dir_option
@option("--all", "-a", is_flag=True, help="Regenerate the whole secret file.")
@option("--server", "-s", is_flag=True, help="Regenerate the server secret.")
@option("--missing", "-m", is_flag=True, help="Only generate the missing peer secrets.")
@option(
    "--peer",
    "-p",
    multiple=True,
    help="Regenerate a specific peer secret. Can be specified multiple times",
)
@option(
    "--overwrite/--no-overwrite",
    is_flag=True,
    help="Whether to overwrite the keys without confirmation.",
)
def generate_keys(interface, config_dir, all, server, missing, peer, overwrite):
    """Generate or regenerate public, private and preshared keys."""
    from .core import WgWizard

    wg_wizard = WgWizard.from_dir(config_dir, interface)
    missing_peers = wg_wizard.generate_keys(
        regenerate_all=all,
        server=server,
        missing=missing,
        peers=peer,
        overwrite=overwrite,
    )
    if missing_peers:
        logger.info("Generated secret for missing peers %s.", missing_peers)
    if all or server or missing_peers or peer:
        wg_wizard.dump(config_dir, interface, config=False)
    else:
        logger.info("Nothing changed.")


@main.command()
@interface_option
@config_dir_option
def check(interface, config_dir):
    """Check whether the wg-wizard config is ready for export."""
    from .core import WgWizard

    WgWizard.from_dir(config_dir, interface).check_secret()


@main.command()
@interface_option
@config_dir_option
@option(
    "--text/--no-text",
    is_flag=True,
    default=True,
    help="Whether to output config text to the stdout.",
)
@option(
    "--qrcode/--no-qrcode",
    is_flag=True,
    help="Whether to output the QR Code to the stdout.",
)
@invert_qrcode_option
def export_server_config(interface, config_dir, text, qrcode, invert_qrcode):
    """Export a wg-quick server config."""
    from .core import export_wg_quick_config_from_files

    export_wg_quick_config_from_files(
        config_dir, interface, text, qrcode, invert_qrcode
    )


@main.command()
@interface_option
@config_dir_option
@option(
    "--name",
    "-n",
    prompt="Name of the peer",
    help="Name of the peer.",
)
@option(
    "--text/--no-text",
    is_flag=True,
    default=True,
    help="Whether to output config text to the stdout.",
)
@option(
    "--qrcode/--no-qrcode",
    is_flag=True,
    default=True,
    help="Whether to output the QR Code to the stdout.",
)
@invert_qrcode_option
def export_client_config(interface, config_dir, name, text, qrcode, invert_qrcode):
    """Export a wg-quick client config."""
    from .core import export_wg_quick_config_from_files

    export_wg_quick_config_from_files(
        config_dir, interface, text, qrcode, invert_qrcode, peer_name=name
    )
