"""tls_probe: URI parsing, the pg SSLRequest preamble, TLS handshake and certificate parsing."""

import asyncio
import datetime
import ssl

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from mcp_database.errors import GuidanceError
from mcp_database.helpers import tls_probe


def _self_signed(days_valid: int, host: str = "localhost"):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=days_valid))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False)
        .sign(key, hashes.SHA256())
    )
    return cert, key


class TestEndpoint:
    @pytest.mark.parametrize(
        ("uri", "expected"),
        [
            ("postgresql://u@host:5433/db", ("postgresql", "host", 5433)),
            ("redis://host/0", ("redis", "host", 6379)),
            ("mongodb://host/app", ("mongodb", "host", 27017)),
            ("rediss://host/0", ("rediss", "host", 6379)),
        ],
    )
    def test_endpoint_of_defaults_the_port(self, uri, expected):
        assert tls_probe.endpoint_of(uri) == expected

    @pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1"])
    def test_is_local(self, host):
        assert tls_probe.is_local(host) is True
        assert tls_probe.is_local("db.example.com") is False


class TestGuidance:
    async def test_sqlite_has_no_endpoint(self):
        with pytest.raises(GuidanceError, match="local file"):
            await tls_probe.probe_tls("sqlite:///tmp/app.db")

    @pytest.mark.parametrize("scheme", ["mysql", "mariadb"])
    async def test_mysql_family_guides_to_openssl(self, scheme):
        with pytest.raises(GuidanceError, match="openssl s_client"):
            await tls_probe.probe_tls(f"{scheme}://u@h:3306/db")


class TestProbe:
    async def test_unreachable_host_is_clean(self):
        result = await tls_probe.probe_tls("postgresql://u@127.0.0.1:1/db", timeout_s=2)
        assert result["reachable"] is False

    async def test_pg_plaintext_server_answers_no(self):
        """A pg-style server answering 'N' to the SSLRequest is reported as TLS off."""

        async def handler(reader, writer):
            await reader.readexactly(8)
            writer.write(b"N")
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            result = await tls_probe.probe_tls(f"postgresql://u@127.0.0.1:{port}/db", timeout_s=5)
        assert result["tls"] is False and "N" in result["note"]

    async def test_tls_server_certificate_is_parsed(self, tmp_path):
        """A real TLS listener's certificate is parsed into issuer/expiry (redis path, direct handshake)."""
        cert, key = _self_signed(days_valid=42)
        cert_pem = tmp_path / "cert.pem"
        cert_pem.write_bytes(
            cert.public_bytes(serialization.Encoding.PEM)
            + key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_pem)

        async def handler(reader, writer):
            await asyncio.sleep(0.05)
            writer.close()

        server = await asyncio.start_server(handler, "127.0.0.1", 0, ssl=context)
        port = server.sockets[0].getsockname()[1]
        async with server:
            result = await tls_probe.probe_tls(f"redis://127.0.0.1:{port}/0", timeout_s=5)
        assert result["tls"] is True
        assert result["certificate"]["days_left"] in (41, 42)
        assert result["certificate"]["self_signed"] is True
        assert "localhost" in result["certificate"]["san"]

    async def test_plaintext_server_on_tls_path_fails_cleanly(self):
        """A plaintext listener on the redis path yields tls=False, never a crash."""

        async def handler(reader, writer):
            writer.write(b"+PONG\r\n")
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            result = await tls_probe.probe_tls(f"redis://127.0.0.1:{port}/0", timeout_s=5)
        assert result["tls"] is False


class TestParseAndTimeout:
    def test_certificate_without_san_parses(self):
        """A certificate lacking a SAN extension yields an empty san list, not an error."""
        from cryptography.hazmat.primitives import serialization

        # a certificate rebuilt without a SAN extension
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "db")])
        now = datetime.datetime.now(datetime.UTC)
        no_san = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(1)
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=30))
            .sign(key, hashes.SHA256())
        )
        parsed = tls_probe._parse_certificate(no_san.public_bytes(serialization.Encoding.DER))
        assert parsed["san"] == [] and parsed["self_signed"] is True

    async def test_hanging_server_times_out_cleanly(self):
        """A server that accepts the socket but never answers is reported as a timeout, not a hang."""
        import socket
        import threading
        import time

        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        held = []

        def hold():
            conn, _ = listener.accept()
            held.append(conn)
            time.sleep(30)  # accept but never respond; the probe's socket timeout must bound the wait

        threading.Thread(target=hold, daemon=True).start()
        result = await tls_probe.probe_tls(f"redis://127.0.0.1:{port}/0", timeout_s=1)
        listener.close()
        for conn in held:
            conn.close()
        assert result["tls"] is False and "never answered" in result["note"]
