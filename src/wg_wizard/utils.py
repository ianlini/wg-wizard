from base64 import standard_b64decode
import binascii
from email.policy import strict
from ipaddress import ip_interface
from pathlib import Path
import shlex
import stat

import click
from pydantic import BaseModel, SecretStr, Extra

from .wg import pubkey


def to_camel(string: str) -> str:
    return "".join(word.capitalize() for word in string.split("_"))


class StrictModel(BaseModel):
    class Config:
        extra = Extra.forbid
        validate_assignment = True
        validate_all = True
        json_encoders = {
            SecretStr: lambda v: v.get_secret_value(),
        }


class StrictCamelModel(StrictModel):
    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True


def ensure_file(path: Path, mode: int, overwrite=False):
    if not path.exists():
        path.touch(mode=mode)
    else:
        if not path.is_file():
            raise ValueError(f"{path} is not a file.")
        if not overwrite:
            click.confirm(
                f"'{path}' already exists. Do you want to overwrite it?", abort=True
            )
        path.chmod(mode=mode)


def check_file_mode(path: Path):
    st_mode = path.stat().st_mode
    if st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise PermissionError(
            f"Permissions 0o{stat.S_IMODE(st_mode):o} for '{path}' are too open. "
            "Setting the mode to 0o600 is recommended."
        )


def format_ini_lines(obj: BaseModel, exclude=None):
    for field_name, field_config in obj.__fields__.items():
        if exclude is not None and field_name in exclude:
            continue
        field_val = getattr(obj, field_name)
        if field_val is None:
            continue
        if isinstance(field_val, list):
            for val in field_val:
                yield f"{field_config.alias} = {val}"
        elif isinstance(field_val, SecretStr):
            yield f"{field_config.alias} = {field_val.get_secret_value()}"
        elif isinstance(field_val, bool):
            yield f"{field_config.alias} = {'true' if field_val else 'false'}"
        else:
            yield f"{field_config.alias} = {field_val}"


def check_key(key: str, error_prefix: strict):
    try:
        decoded = standard_b64decode(key)
    except binascii.Error as exc:
        raise binascii.Error(f"{error_prefix} base64 failed decoding: {exc}")
    if len(decoded) != 32:
        raise ValueError(f"{error_prefix} size is not 32.")


def check_key_pair(private_key: str, public_key: str, error_prefix: str):
    check_key(private_key, f"{error_prefix} private_key")
    check_key(public_key, f"{error_prefix} public_key")
    if pubkey(private_key) != public_key:
        raise ValueError(f"{error_prefix}'s private_key and public_key is not a pair.")


def get_iptables_commands(
    internet_interface_name: str,
    allow_intranet: bool,
    allow_all_server_ip: bool,
    wg_server_interfaces: list[str],
) -> tuple[list[str], list[str]]:
    wg_server_interfaces = [
        ip_interface(interface) for interface in wg_server_interfaces
    ]

    post_up = []
    if internet_interface_name:
        ii_name = shlex.quote(internet_interface_name)
        post_up.append(f"iptables -A FORWARD -i %i -o {ii_name} -j ACCEPT")
        post_up.append(f"iptables -A FORWARD -i {ii_name} -o %i -j ACCEPT")
        for network in set(interface.network for interface in wg_server_interfaces):
            network = shlex.quote(str(network))
            post_up.append(
                f"iptables -t nat -A POSTROUTING -s {network} -o {ii_name} -j MASQUERADE"
            )
    if allow_intranet:
        post_up.append("iptables -A FORWARD -i %i -o %i -j ACCEPT")
    if not allow_all_server_ip:
        for interface in wg_server_interfaces:
            ip = shlex.quote(str(interface.ip))
            post_up.append(f"iptables -A INPUT -d {ip} -i %i -j ACCEPT")
        post_up.append("iptables -A INPUT -i %i -j DROP")

    pre_down = [cmd.replace(" -A ", " -D ", 1) for cmd in post_up]
    return post_up, pre_down
