"""Versioned member protocol; execution token only, no wallet or TIG secrets."""

import json
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class ProtocolError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProtocolError("pool redirected an authenticated request")


class Client:
    version = "2.0"

    def __init__(self, origin, execution_token, *, timeout=20):
        parsed = urlsplit(origin)
        if (parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
            raise ProtocolError("configure an HTTPS pool origin")
        if not execution_token:
            raise ProtocolError("member execution token required")
        self.origin, self.token, self.timeout = origin.rstrip("/"), execution_token, timeout
        self.opener = build_opener(NoRedirect())

    def call(self, method, path, body=None):
        if method not in ("GET", "POST") or not path.startswith("/api/v2/") or ".." in path:
            raise ProtocolError("invalid member API operation")
        encoded = json.dumps(body, separators=(",", ":"), allow_nan=False).encode() if body is not None else None
        request = Request(self.origin + path, data=encoded, method=method, headers={
            "Authorization": "Bearer " + self.token, "X-InnoPool-Version": self.version,
            "Content-Type": "application/json", "Accept": "application/json"})
        with self.opener.open(request, timeout=self.timeout) as response:
            raw = response.read(32*1024*1024+1)
        if len(raw) > 32*1024*1024:
            raise ProtocolError("pool response exceeds the configured limit")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ProtocolError("pool response is not an object")
        return value

    def capabilities(self):
        result = self.call("GET", "/api/v2/capabilities")
        if result.get("api_version") != self.version or result.get("assignment_unit") != "whole-benchmark":
            raise ProtocolError("pool does not support this whole-benchmark API version")
        return result

    def benchmark(self, identity):
        return self.call("GET", "/api/v2/benchmarks/" + quote(identity, safe=""))

    def acknowledge(self, identity, assignment_digest):
        return self.call("POST", "/api/v2/benchmarks/" + quote(identity, safe="") + "/acknowledge",
                         {"assignment_digest": assignment_digest})
