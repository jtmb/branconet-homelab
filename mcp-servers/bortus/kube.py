"""Kubernetes access for the BORTUS MCP.

Two jobs: read exactly the Secret objects a caller names, and expose the
Secret names in a namespace so an agent can discover what exists. The
transport accepts the kubeconfig styles this homelab actually uses
(bearer token, client certificate, or exec-free static config), and every
read is bounded.
"""

import base64
import binascii
import http.client
import json
import os
import ssl
import tempfile
from urllib.parse import urlsplit

MAX_OBJECT_BYTES = 2 * 1024 * 1024
MAX_LIST_BYTES = 4 * 1024 * 1024
MAX_FILE_BYTES = 64 * 1024
MAX_ENV_BYTES = 32 * 1024
MAX_SELECTED_BYTES = 64 * 1024
TIMEOUT = 10


class CredentialError(Exception):
    """A named Secret or key could not be read as required."""


class KubeconfigError(Exception):
    """The kubeconfig is missing, unsafe or not usable."""


class Delivery:
    """One validated value bound for a file or an environment variable."""

    __slots__ = ("kind", "destination", "data")

    def __init__(self, kind, destination, data):
        self.kind = kind
        self.destination = destination
        self.data = data

    def __repr__(self):
        # Never let a value reach a log or a traceback frame.
        return f"Delivery({self.kind!r}, {self.destination!r}, <{len(self.data)} bytes>)"


def _document(path):
    """Read a private kubeconfig as JSON or YAML."""
    from policy import PolicyError, read_private

    try:
        raw = read_private(path, 65536)
    except PolicyError:
        raise KubeconfigError("kubeconfig must be a private file owned by you") from None
    text = raw.decode("utf-8", "replace")
    try:
        return json.loads(text)
    except ValueError:
        pass
    try:
        import yaml
    except ImportError:
        raise KubeconfigError("kubeconfig must be JSON when PyYAML is unavailable") from None
    try:
        document = yaml.safe_load(text)
    except Exception:
        raise KubeconfigError("kubeconfig is not readable YAML or JSON") from None
    if not isinstance(document, dict):
        raise KubeconfigError("kubeconfig is not a mapping")
    return document


def _auth(user):
    """Return ("token", value) or ("cert", cert_pem, key_pem)."""
    if isinstance(user.get("token"), str) and user["token"]:
        if len(user["token"]) > 8192:
            raise KubeconfigError("kubeconfig token is implausible")
        return ("token", user["token"])
    cert, key = user.get("client-certificate-data"), user.get("client-key-data")
    if not (isinstance(cert, str) and isinstance(key, str)):
        raise KubeconfigError("kubeconfig needs a token or a client certificate")
    try:
        cert_pem = base64.b64decode(cert, validate=True)
        key_pem = base64.b64decode(key, validate=True)
    except (binascii.Error, ValueError):
        raise KubeconfigError("kubeconfig client certificate is not base64") from None
    if b"BEGIN CERTIFICATE" not in cert_pem or b"PRIVATE KEY" not in key_pem:
        raise KubeconfigError("kubeconfig client certificate is not PEM")
    return ("cert", cert_pem, key_pem)


def _kubeconfig(path):
    """Return (parsed server, CA bytes, auth) for one kubeconfig."""
    document = _document(path)
    try:
        cluster = document["clusters"][0]["cluster"]
        user = document["users"][0]["user"]
        server, ca = cluster["server"], cluster["certificate-authority-data"]
    except (KeyError, IndexError, TypeError):
        raise KubeconfigError("kubeconfig is incomplete") from None
    parsed = urlsplit(server) if isinstance(server, str) else None
    if parsed is None or parsed.scheme != "https" or not parsed.hostname:
        raise KubeconfigError("kubeconfig must use an https API server")
    try:
        certificate = base64.b64decode(ca, validate=True)
    except (binascii.Error, TypeError, ValueError):
        raise KubeconfigError("kubeconfig CA is not base64") from None
    if b"BEGIN CERTIFICATE" not in certificate:
        raise KubeconfigError("kubeconfig CA is not PEM")
    return parsed, certificate, _auth(user)


class KubeconfigTransport:
    """HTTPS transport pinned to one API server, one CA and one identity."""

    def __init__(self, path):
        server, certificate, auth = _kubeconfig(path)
        self._host = server.hostname
        self._port = server.port or 443
        try:
            self._context = ssl.create_default_context(cadata=certificate.decode("ascii"))
        except UnicodeDecodeError:
            raise KubeconfigError("kubeconfig CA is not ASCII PEM") from None
        self._token = None
        if auth[0] == "token":
            self._token = auth[1]
        else:
            # ssl only loads client certificates from files; keep them in a
            # private directory for the life of this process.
            directory = tempfile.mkdtemp(prefix="bortus-client-")
            os.chmod(directory, 0o700)
            cert_path, key_path = os.path.join(directory, "c.pem"), os.path.join(directory, "k.pem")
            for target, data in ((cert_path, auth[1]), (key_path, auth[2])):
                descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(data)
            self._context.load_cert_chain(cert_path, key_path)

    def get(self, path, limit=MAX_OBJECT_BYTES):
        """Return (status, body) for one bounded GET request."""
        headers = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        connection = http.client.HTTPSConnection(self._host, self._port,
                                                 timeout=TIMEOUT, context=self._context)
        try:
            connection.request("GET", path, headers=headers)
            response = connection.getresponse()
            return response.status, response.read(limit + 1)
        finally:
            connection.close()


class SecretReader:
    """Read Secrets or list their names through a transport."""

    def __init__(self, transport):
        self.transport = transport

    def get(self, namespace, name):
        """Return the object's decoded data, or raise a fixed error."""
        status, body = self.transport.get(
            f"/api/v1/namespaces/{namespace}/secrets/{name}")
        if status == 404:
            raise CredentialError("not_found")
        if status == 403:
            raise CredentialError("forbidden")
        if status != 200 or len(body) > MAX_OBJECT_BYTES:
            raise CredentialError("unavailable")
        try:
            document = json.loads(body)
        except (ValueError, RecursionError):
            raise CredentialError("malformed") from None
        if (not isinstance(document, dict) or document.get("kind") != "Secret"
                or not isinstance(document.get("data"), dict)
                or len(document["data"]) > 1024):
            raise CredentialError("malformed")
        decoded = {}
        for key, value in document["data"].items():
            if not isinstance(value, str):
                raise CredentialError("malformed")
            try:
                decoded[key] = base64.b64decode(value, validate=True)
            except (binascii.Error, ValueError):
                raise CredentialError("malformed") from None
        return decoded

    def names(self, namespace):
        """Return the Secret names in one namespace."""
        status, body = self.transport.get(
            f"/api/v1/namespaces/{namespace}/secrets", MAX_LIST_BYTES)
        if status == 403:
            raise CredentialError("forbidden")
        if status != 200 or len(body) > MAX_LIST_BYTES:
            raise CredentialError("unavailable")
        try:
            document = json.loads(body)
        except (ValueError, RecursionError):
            raise CredentialError("malformed") from None
        items = document.get("items") if isinstance(document, dict) else None
        if not isinstance(items, list) or len(items) > 2000:
            raise CredentialError("malformed")
        return sorted(item["metadata"]["name"] for item in items
                      if isinstance(item, dict) and isinstance(item.get("metadata"), dict)
                      and isinstance(item["metadata"].get("name"), str))


def as_text(data):
    """Return (text, binary) for one decoded value."""
    try:
        return data.decode("utf-8"), False
    except UnicodeDecodeError:
        return base64.b64encode(data).decode(), True


class SecretSource:
    """Read validated Secret objects through an injected transport."""

    def __init__(self, transport):
        self.transport = transport

    def fetch(self, bindings):
        """Return {(namespace, name): parsed object} for the named Secrets."""
        paths = {}
        for binding in bindings:
            paths[(binding["namespace"], binding["secret"])] = (
                "/api/v1/namespaces/{0}/secrets/{1}".format(
                    binding["namespace"], binding["secret"]))
        objects = {}
        for reference, path in paths.items():
            status, body = self.transport.get(path)
            if status == 404:
                raise CredentialError("missing")
            if status != 200 or len(body) > MAX_OBJECT_BYTES:
                raise CredentialError("unavailable")
            try:
                document = json.loads(body)
            except (ValueError, RecursionError):
                raise CredentialError("malformed") from None
            if (not isinstance(document, dict) or document.get("kind") != "Secret"
                    or not isinstance(document.get("data"), dict)
                    or len(document["data"]) > 1024):
                raise CredentialError("malformed")
            objects[reference] = document
        return objects


def materialize(bindings, objects):
    """Return the Deliveries for one profile, enforcing every size limit."""
    deliveries, total = [], 0
    for binding in bindings:
        document = objects.get((binding["namespace"], binding["secret"]))
        if document is None:
            raise CredentialError("missing")
        encoded = document["data"].get(binding["key"])
        if not isinstance(encoded, str):
            raise CredentialError("missing")
        try:
            value = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise CredentialError("malformed") from None
        if binding["delivery"] == "env":
            if len(value) > MAX_ENV_BYTES or b"\x00" in value:
                raise CredentialError("malformed")
            try:
                value.decode("utf-8")
            except UnicodeDecodeError:
                raise CredentialError("malformed") from None
        elif len(value) > MAX_FILE_BYTES:
            raise CredentialError("too_large")
        total += len(value)
        if total > MAX_SELECTED_BYTES:
            raise CredentialError("too_large")
        deliveries.append(Delivery(binding["delivery"], binding["destination"], value))
    return deliveries
