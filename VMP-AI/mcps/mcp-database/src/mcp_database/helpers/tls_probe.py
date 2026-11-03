from __future__ import annotations

import asyncio
import socket
import ssl
import struct
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from ..errors import GuidanceError

_PG_SSLREQUEST = struct.pack("!II", 8, 80877103)
_DEFAULT_PORTS = {"postgres": 5432, "postgresql": 5432, "mongodb": 27017, "redis": 6379, "rediss": 6379}
_LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


def endpoint_of(uri: str) -> tuple[str, str, int]:
    """(scheme, host, port) of the URI, defaulting the port per engine."""
    parts = urlsplit(uri)
    scheme = parts.scheme.lower()
    host = parts.hostname or "localhost"
    return scheme, host, parts.port or _DEFAULT_PORTS.get(scheme, 0)


def is_local(host: str) -> bool:
    return host in _LOCAL_HOSTS


def _parse_certificate(der: bytes) -> dict[str, Any]:
    """Subject/issuer/SANs/validity out of the DER certificate (cryptography does the ASN.1)."""
    from cryptography import x509

    cert = x509.load_der_x509_certificate(der)
    try:
        sans = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(
            x509.DNSName
        )
    except x509.ExtensionNotFound:
        sans = []
    not_after = cert.not_valid_after_utc
    return {
        "subject": cert.subject.rfc4514_string(),
        "issuer": cert.issuer.rfc4514_string(),
        "san": sans,
        "not_before": cert.not_valid_before_utc.isoformat(),
        "not_after": not_after.isoformat(),
        "days_left": (not_after - datetime.now(UTC)).days,
        "self_signed": cert.subject == cert.issuer,
    }


def _probe_sync(scheme: str, host: str, port: int, timeout_s: int) -> dict[str, Any]:
    """Blocking TLS inspection with hard socket timeouts (run in a thread; no partial-handshake hangs).

    postgres sends its SSLRequest first ('S'/'N'); the direct-TLS engines wrap the raw socket. Nothing is
    verified — we read what the server presents, self-signed chains included.
    """
    base = {"host": host, "port": port, "scheme": scheme}
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=timeout_s) as raw:
            raw.settimeout(timeout_s)
            if scheme in ("postgres", "postgresql"):
                raw.sendall(_PG_SSLREQUEST)
                if raw.recv(1) != b"S":
                    return {**base, "tls": False, "note": "server answered the SSLRequest with 'N' (TLS off)"}
            with context.wrap_socket(raw, server_hostname=host) as tls:
                der = tls.getpeercert(binary_form=True)
                result: dict[str, Any] = {**base, "tls": True, "protocol": tls.version()}
                cipher = tls.cipher()
                result["cipher"] = cipher[0] if cipher else None
                if der:
                    result["certificate"] = _parse_certificate(der)
                return result
    except ssl.SSLError as exc:
        return {**base, "tls": False, "note": f"server did not complete a TLS handshake ({type(exc).__name__})"}
    except TimeoutError:
        return {**base, "tls": False, "note": "server never answered the TLS handshake (plaintext listener?)"}
    except OSError as exc:
        return {**base, "reachable": False, "note": f"could not reach the server ({exc.__class__.__name__})"}


async def probe_tls(uri: str, *, timeout_s: int = 10) -> dict[str, Any]:
    """What the server at the URI offers over TLS: support, protocol, cipher and certificate expiry.

    postgres speaks its SSLRequest preamble first; mongodb/redis/rediss accept (or cleanly fail) a direct
    TLS handshake. No credentials are used and nothing is verified — this inspects what the server presents.
    """
    scheme, host, port = endpoint_of(uri)
    if scheme == "sqlite":
        raise GuidanceError("SQLite is a local file: there is no TLS endpoint to inspect")
    if scheme in ("mysql", "mariadb"):
        raise GuidanceError(
            "MySQL/MariaDB negotiate TLS after the auth handshake; inspect with: "
            "openssl s_client -connect host:3306 -starttls mysql"
        )
    return await asyncio.to_thread(_probe_sync, scheme, host, port, timeout_s)
