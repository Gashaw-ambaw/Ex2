"""Reads a public GitHub repo (F5): the file list with sizes and the README. It only reads, and runs nothing.
The only outside addresses the repo check opens are the two hosts below."""
import re
from urllib.parse import quote, urlsplit

import httpx

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
TIMEOUT_SEC = 10


class NotFound(Exception):
    """The repo or file is private, missing or blocked."""


class Limited(Exception):
    """GitHub limits requests, is down or gave a damaged answer."""


def clean_url(text):
    """"owner/repo" from an https://github.com/owner/repo link, or None."""
    try:
        parts = urlsplit(text.strip())
    except ValueError:
        return None
    # netloc must be the host alone: no user name and no port.
    if parts.scheme != "https" or parts.netloc.lower() != "github.com":
        return None
    names = parts.path.strip("/").split("/")
    if len(names) < 2:
        return None
    owner, repo = names[0], names[1].removesuffix(".git")
    if not re.fullmatch(r"[A-Za-z0-9-]+", owner) or not re.fullmatch(r"[A-Za-z0-9._-]+", repo):
        return None
    if repo in (".", ".."):
        return None
    return f"{owner}/{repo}"


def _limit_reached(reply):
    if reply.status_code == 429 or reply.status_code >= 500:
        return True
    if reply.status_code != 403:
        return False
    return reply.headers.get("x-ratelimit-remaining") == "0" or "rate limit" in reply.text.lower()


class GitHubClient:
    def __init__(self, token=None, http=None):
        # Without a token GitHub allows fewer requests per hour.
        self._token = (token or "").strip()
        # Tests pass a client with a fake network.
        self._http = http or httpx.Client(timeout=TIMEOUT_SEC)

    def _get(self, address, headers=None):
        try:
            # follow_redirects: a renamed repo answers with a redirect.
            reply = self._http.get(address, headers=headers, follow_redirects=True)
        except httpx.HTTPError:
            raise Limited() from None
        if _limit_reached(reply):
            raise Limited()
        return reply

    def tree(self, repo):
        """The files of the default branch as a list of (path, size in bytes). One API request."""
        headers = {"Accept": "application/vnd.github+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        reply = self._get(f"{API}/repos/{repo}/git/trees/HEAD?recursive=1", headers)
        if reply.status_code == 409:  # An empty repo.
            return []
        if reply.status_code != 200:
            raise NotFound()
        try:
            return [(f["path"], f.get("size", 0)) for f in reply.json()["tree"] if f["type"] == "blob"]
        except (ValueError, KeyError, TypeError):
            raise Limited() from None

    def readme(self, repo, path):
        """The text of one file, from the raw host (no token, not part of the API limit)."""
        reply = self._get(f"{RAW}/{repo}/HEAD/{quote(path)}")
        if reply.status_code != 200:
            raise NotFound()
        return reply.content.decode("utf-8-sig", errors="replace")
