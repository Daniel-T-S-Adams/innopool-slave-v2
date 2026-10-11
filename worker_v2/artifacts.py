"""Public binary downloads never forward execution credentials."""

from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request

from .state import StateError


DEFAULT_BINARY_HOSTS = ("mainnet-api.tig.foundation", "media.githubusercontent.com")


def check_url(url, allowed_hosts):
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as failure:
        raise StateError('algorithm URL is malformed') from failure
    if (parsed.scheme != "https" or parsed.hostname not in allowed_hosts
            or parsed.username or parsed.password or parsed.fragment
            or port not in (None, 443)
            or (parsed.hostname == "media.githubusercontent.com"
                and (not parsed.path.startswith("/media/tig-foundation/tig-monorepo/")
                     or '\\' in unquote(parsed.path)
                     or any(part in ('.', '..') for part in unquote(parsed.path).split('/'))))):
        raise StateError("algorithm download does not use an allowed public HTTPS source")


class ArtifactRedirect(HTTPRedirectHandler):
    def __init__(self, allowed_hosts):
        self.allowed_hosts = set(allowed_hosts)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if req.get_method() != "GET":
            raise StateError("only public algorithm GET requests may redirect")
        check_url(newurl, self.allowed_hosts)
        return Request(newurl, headers={"User-Agent": "innopool-v2-member/2.0"}, method="GET")
