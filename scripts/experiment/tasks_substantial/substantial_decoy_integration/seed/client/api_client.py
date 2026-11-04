import urllib.request


class ApiClient:
    """A minimal HTTP client with no caching yet — every call hits the network."""

    def fetch(self, url: str, timeout: float = 5.0) -> str:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
