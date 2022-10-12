from itertools import chain
from typing import Literal, Optional

from pydantic import Field, IPvAnyInterface, IPvAnyAddress, SecretStr

from .utils import StrictCamelModel, format_ini_lines


class WgQuickInterfaceConfig(StrictCamelModel):
    private_key: SecretStr
    listen_port: Optional[int]
    fw_mark: Optional[Literal["off"] | int]
    address: list[IPvAnyInterface] = Field(min_items=1)
    dns: list[IPvAnyAddress] = Field(alias="DNS")
    mtu: Optional[int] = Field(alias="MTU")
    table: Optional[str]
    pre_up: list[str]
    post_up: list[str]
    pre_down: list[str]
    post_down: list[str]
    save_config: Optional[bool]

    def format_ini_lines(self) -> list[str]:
        yield "[Interface]"
        yield from format_ini_lines(self)


class WgQuickPeerConfig(StrictCamelModel):
    comment: Optional[str]
    public_key: str
    preshared_key: Optional[SecretStr]
    allowed_ips: list[IPvAnyInterface] = Field(alias="AllowedIPs", min_items=1)
    endpoint: Optional[str]
    persistent_keepalive: Optional[Literal["off"] | int]

    def format_ini_lines(self) -> list[str]:
        yield "[Peer]"
        if self.comment is not None:
            yield f"# {self.comment}"
        yield from format_ini_lines(self, exclude={"comment"})


class WgQuickConfig(StrictCamelModel):
    interface: WgQuickInterfaceConfig
    peer: list[WgQuickPeerConfig]

    def format_ini(self) -> str:
        def check(s):
            assert "\n" not in s
            return s

        ini_str = "\n".join(
            check(s)
            for s in chain(
                self.interface.format_ini_lines(),
                *(chain(("",), peer.format_ini_lines()) for peer in self.peer),
            )
        )
        return ini_str
