"""Thin wrapper around the RouterOS API (librouteros)."""
import ssl
import threading
from typing import Any

from librouteros import connect
from librouteros.exceptions import LibRouterosError

from . import config


class MikroTikError(Exception):
    pass


class MikroTik:
    """Opens a short-lived connection per request (simple and robust against dropped links)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def _connect(self):
        kwargs: dict[str, Any] = dict(
            host=config.MT_HOST,
            username=config.MT_USER,
            password=config.MT_PASSWORD,
            port=config.MT_PORT,
            timeout=config.MT_TIMEOUT,
        )
        if config.MT_SSL:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE  # RouterOS usually has a self-signed certificate
            if config.MT_SSL_ADH:  # api-ssl without a certificate assigned on the router
                ctx.set_ciphers("ADH:@SECLEVEL=0")
            kwargs["ssl_wrapper"] = ctx.wrap_socket
        try:
            return connect(**kwargs)
        except (LibRouterosError, OSError) as e:
            raise MikroTikError(f"Cannot connect to MikroTik: {e}") from e

    def _run(self, fn):
        with self._lock:
            api = self._connect()
            try:
                return fn(api)
            except (LibRouterosError, OSError) as e:
                raise MikroTikError(str(e)) from e
            finally:
                api.close()

    def dhcp_servers(self) -> list[dict]:
        """DHCP servers = LANs visible from the router (server name -> interface)."""
        def go(api):
            return [
                {
                    "name": s.get("name", ""),
                    "interface": s.get("interface", ""),
                    "disabled": s.get("disabled", False),
                }
                for s in api.path("ip", "dhcp-server")
            ]
        return self._run(go)

    def leases(self) -> list[dict]:
        def go(api):
            return [dict(r) for r in api.path("ip", "dhcp-server", "lease")]
        return self._run(go)

    def wol(self, interface: str, mac: str) -> None:
        def go(api):
            tuple(api("/tool/wol", interface=interface, mac=mac))
        self._run(go)


def get_client() -> MikroTik:
    return MikroTik()
