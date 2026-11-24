"""Local web-server settings and same-network URLs; no network requests."""
import ipaddress
import json
import os
import socket
import subprocess


_LAN_NETWORKS = tuple(ipaddress.ip_network(value) for value in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


def server_settings():
    host = os.environ.get("SONGTOLEARN_HOST", "0.0.0.0").strip()
    port = int(os.environ.get("SONGTOLEARN_PORT", "5000"))
    if not host:
        raise ValueError("SONGTOLEARN_HOST must not be empty")
    if not 1 <= port <= 65535:
        raise ValueError("SONGTOLEARN_PORT must be between 1 and 65535")
    return host, port


def _is_lan(address):
    try:
        ip = ipaddress.ip_address(address)
        return any(ip in network for network in _LAN_NETWORKS)
    except ValueError:
        return False


def lan_addresses():
    # A VPN can also have a default gateway. Rank physical adapters first using
    # Windows metadata, rather than relying on interface names or lookup order.
    if os.name == "nt":
        command = (
            "$physical = @(Get-NetAdapter -Physical -ErrorAction Stop | "
            "Select-Object -ExpandProperty InterfaceIndex); "
            "Get-NetIPConfiguration | Where-Object { "
            "$_.IPv4DefaultGateway.NextHop -and "
            "$_.IPv4DefaultGateway.NextHop -ne '0.0.0.0' } | "
            "ForEach-Object { [pscustomobject]@{ "
            "Name=$_.InterfaceAlias; Address=$_.IPv4Address.IPAddress; "
            "Physical=$physical -contains $_.InterfaceIndex } } | "
            "ConvertTo-Json -Compress"
        )
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True, text=True, timeout=8,
                creationflags=subprocess.CREATE_NO_WINDOW, check=True)
            rows = json.loads(result.stdout or "[]")
            if isinstance(rows, dict):
                rows = [rows]
            addresses = []
            for row in rows:
                values = row.get("Address", [])
                if isinstance(values, str):
                    values = [values]
                for address in values:
                    if _is_lan(address):
                        addresses.append((row.get("Physical") is not True,
                                          row.get("Name", "network"), address))
            if addresses:
                return [(name, address) for _, name, address in sorted(set(addresses))]
        except (OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError):
            pass
    try:
        addresses = {row[4][0] for row in socket.getaddrinfo(
            socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM)}
    except OSError:
        return []
    return [("network candidate", address) for address in sorted(addresses) if _is_lan(address)]


CERT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "https")


def https_cert():
    """Return (cert, key) paths for a self-signed cert covering localhost and this PC's LAN IPs.

    Kept on disk so the phone trusts it once; regenerated only when a LAN address it doesn't cover
    appears (the phone then needs the new cert from /cert)."""
    import datetime
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    cert_path, key_path = os.path.join(CERT_DIR, "cert.pem"), os.path.join(CERT_DIR, "key.pem")
    wanted = {ipaddress.ip_address("127.0.0.1")} | {
        ipaddress.ip_address(address) for _, address in lan_addresses()}
    if os.path.exists(cert_path) and os.path.exists(key_path):
        with open(cert_path, "rb") as f:
            existing = x509.load_pem_x509_certificate(f.read())
        covered = set(existing.extensions.get_extension_for_class(
            x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress))
        if wanted <= covered and existing.not_valid_after_utc > datetime.datetime.now(datetime.UTC):
            return cert_path, key_path

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Song to Learn (local)")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            # iOS rejects TLS certs valid for more than 825 days, even user-trusted ones.
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=800))
            .add_extension(x509.SubjectAlternativeName(
                [x509.DNSName("localhost")] + [x509.IPAddress(ip) for ip in sorted(wanted)]), critical=False)
            # CA:TRUE is what lets iOS show it under Certificate Trust Settings.
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(key, hashes.SHA256()))
    os.makedirs(CERT_DIR, exist_ok=True)
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()))
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    print("  New HTTPS certificate: re-install it on your phone from /cert.", flush=True)
    return cert_path, key_path


def print_urls(host, port, scheme="http"):
    print("Song to Learn", flush=True)
    if host in ("0.0.0.0", "127.0.0.1", "localhost"):
        print(f"  This computer: {scheme}://127.0.0.1:{port}", flush=True)
    if host == "0.0.0.0":
        addresses = lan_addresses()
        for name, address in addresses:
            print(f"  Phone on same Wi-Fi ({name}): {scheme}://{address}:{port}", flush=True)
        if not addresses:
            print(f"  Phone: use this computer's Wi-Fi IPv4 address on port {port} (ipconfig).", flush=True)
        print("  Keep this window open; use a trusted network (the app has no login).", flush=True)
    elif host in ("127.0.0.1", "localhost"):
        print("  Localhost only (SONGTOLEARN_HOST); phone access is disabled.", flush=True)
    else:
        address = f"[{host}]" if ":" in host else host
        print(f"  Configured address: http://{address}:{port}", flush=True)
