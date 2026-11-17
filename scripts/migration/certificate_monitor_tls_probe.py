"""Read a live TLS endpoint's own leaf certificate expiry.

No host filesystem access, no credentials, no privilege beyond an outbound
TLS handshake. This is how kubeadm/kubelet serving certificate expiry is
watched without granting the monitor host or root access: the certificate a
server is currently presenting is itself the fact being observed.
"""
import datetime as dt
import re
import socket
import ssl

_HOSTNAME_RE = re.compile(r"\A[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?\Z")


class ProbeError(RuntimeError):
    """Fixed public codes only; never leak connection/backend detail."""


def probe_tls_expiry(host, port, *, timeout=5):
    """Connect to host:port, read the presented leaf certificate's notAfter.

    Certificate validation is intentionally not performed: the goal is to
    observe what is currently served (including an unexpectedly self-signed
    or expired leaf), not to assert trust. validateNamespace-style strict
    input checks still apply to the connection target itself.
    """
    if not isinstance(host, str) or not _HOSTNAME_RE.match(host):
        raise ProbeError("tls_probe_host_invalid")
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ProbeError("tls_probe_port_invalid")
    context = ssl._create_unverified_context()
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as tls:
                der = tls.getpeercert(binary_form=True)
    except Exception:
        raise ProbeError("tls_probe_unreachable") from None
    if not der:
        raise ProbeError("tls_probe_no_certificate")
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        certificate = x509.load_der_x509_certificate(der, default_backend())
        expiry = certificate.not_valid_after_utc if hasattr(certificate, "not_valid_after_utc") else \
            certificate.not_valid_after.replace(tzinfo=dt.timezone.utc)
    except Exception:
        raise ProbeError("tls_probe_certificate_unparseable") from None
    return {"notAfter": expiry.isoformat().replace("+00:00", "Z")}
