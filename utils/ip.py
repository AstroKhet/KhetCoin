import ipaddress
import miniupnpc

import logging

log = logging.getLogger(__name__)


def str_ip(addr: tuple, name="") -> str:
    if name:
        return f"[{name}]->{addr[0]}:{addr[1]}"
    else:
        return f"{addr[0]}:{addr[1]}"


def encode_ip(ip: bytes | str | int) -> bytes:
    """Encode IP (str, bytes, or int) into 16-byte Bitcoin format."""
    ip_obj = ipaddress.ip_address(ip)

    if isinstance(ip_obj, ipaddress.IPv4Address):
        return b"\x00" * 10 + b"\xff" * 2 + ip_obj.packed
    else:
        return ip_obj.packed


def format_ip(ip_bytes: bytes) -> str:
    """Convert 16-byte or 4-byte Bitcoin IP format to string."""
    if len(ip_bytes) == 4:
        return str(ipaddress.IPv4Address(ip_bytes))

    elif len(ip_bytes) == 16:
        if ip_bytes[:12] == b"\x00" * 10 + b"\xff" * 2:  # IPv6 mapped IPv4
            return str(ipaddress.IPv4Address(ip_bytes[12:]))
        else:
            return str(ipaddress.IPv6Address(ip_bytes))

    else:
        return ""


def is_routable(ip_bytes: bytes | str | int) -> bool:
    # return True
    try:
        ip = ipaddress.ip_address(ip_bytes)
    except ValueError:
        return False

    return (
        not ip.is_private
        and not ip.is_loopback
        and not ip.is_multicast
        and not ip.is_reserved
        and not ip.is_link_local
        and not ip.is_unspecified
    )

def setup_port_forwarding(port, name):
    try:
        upnp = miniupnpc.UPnP()
        upnp.discoverdelay = 200
        upnp.discover()
        upnp.selectigd()
        upnp.addportmapping(
            port, "TCP",
            upnp.lanaddr, port,
            f"{name}'s Node", ""
        )
    except Exception as e:
        log.warning(f"UPnP port forwarding failed: {e}")
        return None

    return upnp.externalipaddress()