"""db_perf_tls against real TLS-enabled servers: the certificate is parsed from a live handshake.

Closes the gap the unit tests cannot: PostgreSQL's full SSLRequest 'S' -> upgrade -> cert path, and a
real database presenting a real certificate, not a bare test listener.
"""

import datetime

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

from mcp_database.helpers import tls_probe

from .conftest import MONGO_IMAGE, PG_IMAGE, REDIS_IMAGE

pytestmark = [pytest.mark.integration, pytest.mark.cross_engine]

_VALID_DAYS = 90


@pytest.fixture(scope="module")
def tls_certs(tmp_path_factory):
    """A self-signed server certificate + key written as PEM files for the containers to serve."""
    certs = tmp_path_factory.mktemp("tls-certs")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "mcp-database-test")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=_VALID_DAYS))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .sign(key, hashes.SHA256())
    )
    (certs / "server.crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (certs / "server.key").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return certs


async def _probe_until_reachable(uri: str, *, attempts: int = 20):
    """Probe the endpoint, retrying while the container is still binding its port (no 'tls' key yet)."""
    import asyncio

    for _ in range(attempts):
        result = await tls_probe.probe_tls(uri, timeout_s=10)
        if "tls" in result:
            return result
        await asyncio.sleep(1)
    return result


async def test_redis_tls_certificate_is_parsed(tls_certs):
    """A TLS-only Redis presents its certificate; the probe parses issuer, expiry and self-signed."""
    boot = (
        "cp /certs/server.crt /certs/server.key /tmp/ && chmod 644 /tmp/server.crt && chmod 640 /tmp/server.key && "
        "exec redis-server --port 0 --tls-port 6379 --tls-cert-file /tmp/server.crt "
        "--tls-key-file /tmp/server.key --tls-ca-cert-file /tmp/server.crt --tls-auth-clients no"
    )
    container = (
        DockerContainer(REDIS_IMAGE)
        .with_volume_mapping(str(tls_certs), "/certs")
        .with_command(["sh", "-c", boot])
        .with_exposed_ports(6379)
    )
    with container:
        wait_for_logs(container, "Ready to accept connections tls", timeout=60)
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        result = await _probe_until_reachable(f"redis://{host}:{port}/0")
    assert result["tls"] is True
    assert result["protocol"].startswith("TLSv1")
    cert = result["certificate"]
    assert cert["self_signed"] is True
    assert "mcp-database-test" in cert["issuer"]
    assert _VALID_DAYS - 2 <= cert["days_left"] <= _VALID_DAYS


async def test_mongo_tls_certificate_is_parsed(tls_certs):
    """A requireTLS mongod presents its certificate on the direct handshake; the probe parses it."""
    boot = (
        "cat /certs/server.crt /certs/server.key > /tmp/server.pem && cp /certs/server.crt /tmp/ca.crt && "
        "chmod 644 /tmp/server.pem /tmp/ca.crt && chown mongodb /tmp/server.pem /tmp/ca.crt && "
        "exec docker-entrypoint.sh mongod --tlsMode requireTLS --tlsCertificateKeyFile /tmp/server.pem "
        "--tlsCAFile /tmp/ca.crt --tlsAllowConnectionsWithoutCertificates --bind_ip_all"
    )
    container = (
        DockerContainer(MONGO_IMAGE)
        .with_volume_mapping(str(tls_certs), "/certs")
        .with_command(["sh", "-c", boot])
        .with_exposed_ports(27017)
    )
    with container:
        wait_for_logs(container, "Waiting for connections", timeout=60)
        host = container.get_container_host_ip()
        port = container.get_exposed_port(27017)
        result = await _probe_until_reachable(f"mongodb://{host}:{port}/test")
    assert result["tls"] is True
    assert result["protocol"].startswith("TLSv1")
    assert result["certificate"]["self_signed"] is True
    assert "mcp-database-test" in result["certificate"]["issuer"]
    assert result["certificate"]["days_left"] >= _VALID_DAYS - 2


async def test_postgres_ssl_request_upgrade_and_certificate(tls_certs):
    """PostgreSQL answers the SSLRequest with 'S', the probe upgrades and parses the served certificate."""
    boot = (
        "cp /certs/server.crt /tmp/server.crt && cp /certs/server.key /tmp/server.key && "
        "chmod 600 /tmp/server.key && chown postgres /tmp/server.key /tmp/server.crt && "
        "exec docker-entrypoint.sh postgres -c ssl=on "
        "-c ssl_cert_file=/tmp/server.crt -c ssl_key_file=/tmp/server.key"
    )
    container = (
        DockerContainer(PG_IMAGE)
        .with_env("POSTGRES_USER", "test")
        .with_env("POSTGRES_PASSWORD", "test")
        .with_env("POSTGRES_DB", "test")
        .with_volume_mapping(str(tls_certs), "/certs")
        .with_command(["sh", "-c", boot])
        .with_exposed_ports(5432)
    )
    with container:
        wait_for_logs(container, r'listening on IPv4 address "0.0.0.0"', timeout=60)
        host = container.get_container_host_ip()
        port = container.get_exposed_port(5432)
        result = await _probe_until_reachable(f"postgresql://test@{host}:{port}/test")
    assert result["tls"] is True
    assert result["protocol"].startswith("TLSv1")
    assert result["certificate"]["self_signed"] is True
    assert result["certificate"]["days_left"] >= _VALID_DAYS - 2
