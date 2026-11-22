"""Small HTTP helpers on top of urllib, which validates certificates with the OS store."""
from __future__ import annotations

import shutil
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_CONTEXT = ssl.create_default_context()
_HEADERS = {"User-Agent": "flinch"}


def open_url(url: str, params: dict | None = None, timeout: float = 600.0, retries: int = 3):
    """Open ``url`` (with optional query parameters), retrying on transient network errors."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers=_HEADERS)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            return urllib.request.urlopen(request, timeout=timeout, context=_CONTEXT)
        except urllib.error.HTTPError as exc:
            if exc.code < 500:  # a client error will not go away by retrying
                raise
            last_error = exc
        except OSError as exc:  # URLError, timeouts, connection resets
            last_error = exc
        time.sleep(2.0 * (attempt + 1))
    raise ConnectionError(f"could not fetch {url}: {last_error}") from last_error


def fetch_text(url: str, params: dict | None = None, **kwargs) -> str:
    """Return the body of ``url`` decoded as UTF-8."""
    with open_url(url, params, **kwargs) as response:
        return response.read().decode("utf-8", errors="replace")


def download(url: str, destination: Path, overwrite: bool = False) -> Path:
    """Download ``url`` to ``destination`` (skipped if the file exists and ``overwrite`` is False)."""
    destination = Path(destination)
    if destination.exists() and not overwrite:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    with open_url(url) as response, open(partial, "wb") as handle:
        shutil.copyfileobj(response, handle)
        expected = response.headers.get("Content-Length")
    if expected is not None and partial.stat().st_size != int(expected):  # the connection was cut
        size = partial.stat().st_size
        partial.unlink(missing_ok=True)
        raise ConnectionError(f"incomplete download of {url}: {size} of {expected} bytes")
    partial.replace(destination)
    return destination
