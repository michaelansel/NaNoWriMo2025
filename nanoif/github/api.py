"""A minimal GitHub REST client for the workflow jobs.

Only the calls the workflows need: issue comments, check runs, reactions, one pull
request, and a collaborator's permission. Every request has a timeout; every failure
is a :class:`GitHubError`. The HTTP layer is a :class:`Transport` so tests run with a
fake and never reach the network.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from nanoif.errors import NanoifError

DEFAULT_API_URL = "https://api.github.com"
DEFAULT_TIMEOUT_S = 30.0
PER_PAGE = 100
MAX_PAGES = 50
ANNOTATION_BATCH = 50
BOT_LOGIN = "github-actions[bot]"
# GitHub rejects check-run output fields longer than this.
MAX_OUTPUT_CHARS = 65535

_NEXT_LINK = re.compile(r'<([^>]+)>\s*;\s*rel="next"')


class GitHubError(NanoifError):
    """A GitHub API call failed, timed out, or returned something unusable."""

    def __init__(self, message: str, status: int | None = None) -> None:
        """Create the error.

        Args:
            message: What failed, including the method and path.
            status: The HTTP status, when a response arrived.
        """
        super().__init__(message)
        self.status = status


class GitHubConfigError(GitHubError):
    """The environment lacks what the client needs (token, repository)."""


@dataclass(frozen=True)
class Request:
    """One HTTP request as the transport sees it."""

    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes | None
    timeout: float


@dataclass(frozen=True)
class Response:
    """One HTTP response as the transport returns it."""

    status: int
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes = b""


Transport = Callable[[Request], Response]


def urllib_transport(request: Request) -> Response:
    """Send a request with ``urllib``; HTTP error statuses are returned, not raised.

    Args:
        request: The request.

    Returns:
        The response, including 4xx/5xx statuses.

    Raises:
        GitHubError: On a network failure or timeout.
    """
    req = urllib.request.Request(
        request.url, data=request.body, method=request.method, headers=dict(request.headers)
    )
    try:
        with urllib.request.urlopen(req, timeout=request.timeout) as resp:
            return Response(resp.status, dict(resp.headers.items()), resp.read())
    except urllib.error.HTTPError as exc:
        return Response(exc.code, dict(exc.headers.items()) if exc.headers else {}, exc.read())
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise GitHubError(f"{request.method} {request.url}: {exc}") from exc


def _header(headers: Mapping[str, str], name: str) -> str:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return ""


class GitHubAPI:
    """GitHub REST calls scoped to one repository."""

    def __init__(
        self,
        token: str,
        repository: str,
        api_url: str = DEFAULT_API_URL,
        transport: Transport = urllib_transport,
        timeout: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        """Create a client.

        Args:
            token: A token with the permissions the calls need (``GITHUB_TOKEN``).
            repository: ``owner/name``.
            api_url: The REST root, ``GITHUB_API_URL`` in Actions.
            transport: The HTTP layer; tests pass a fake.
            timeout: Seconds per request.

        Raises:
            GitHubConfigError: If the token is empty or the repository is not ``owner/name``.
        """
        if not token:
            raise GitHubConfigError("GITHUB_TOKEN is not set")
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository or ""):
            raise GitHubConfigError(f"GITHUB_REPOSITORY must be owner/name, got {repository!r}")
        self.token = token
        self.repository = repository
        self.api_url = api_url.rstrip("/")
        self.transport = transport
        self.timeout = timeout

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None, transport: Transport = urllib_transport
    ) -> GitHubAPI:
        """Build a client from ``GITHUB_TOKEN``, ``GITHUB_REPOSITORY`` and ``GITHUB_API_URL``.

        Args:
            env: Mapping to read; defaults to ``os.environ``.
            transport: The HTTP layer.

        Returns:
            The client.

        Raises:
            GitHubConfigError: If a required variable is missing.
        """
        env = os.environ if env is None else env
        return cls(
            token=env.get("GITHUB_TOKEN", ""),
            repository=env.get("GITHUB_REPOSITORY", ""),
            api_url=env.get("GITHUB_API_URL", "") or DEFAULT_API_URL,
            transport=transport,
        )

    # -- transport -----------------------------------------------------------------

    def _url(self, path: str) -> str:
        return path if path.startswith("http") else f"{self.api_url}{path}"

    def _send(self, method: str, url: str, payload: Any = None) -> Response:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "nanoif",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        return self.transport(Request(method, url, headers, body, self.timeout))

    def request(self, method: str, path: str, payload: Any = None) -> Any:
        """Send one request and return the decoded JSON body.

        Args:
            method: HTTP method.
            path: Path under the API root (``/repos/...``) or an absolute URL.
            payload: JSON body, if any.

        Returns:
            The decoded body, or ``None`` for an empty body.

        Raises:
            GitHubError: On a non-2xx status or a body that is not JSON.
        """
        response = self._send(method, self._url(path), payload)
        return self._decode(method, path, response)

    @staticmethod
    def _decode(method: str, path: str, response: Response) -> Any:
        if not 200 <= response.status < 300:
            detail = response.body.decode("utf-8", "replace")[:300]
            raise GitHubError(f"{method} {path}: HTTP {response.status}: {detail}", response.status)
        if not response.body:
            return None
        try:
            return json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitHubError(f"{method} {path}: response is not JSON: {exc}") from exc

    def paginate(self, path: str) -> Iterator[Any]:
        """Yield every item of a list endpoint, following ``Link: rel="next"``.

        Args:
            path: The list endpoint; ``per_page`` is added.

        Yields:
            Each item across pages.

        Raises:
            GitHubError: On a failed page, a non-list page, or more than ``MAX_PAGES`` pages.
        """
        separator = "&" if "?" in path else "?"
        url: str | None = self._url(f"{path}{separator}per_page={PER_PAGE}")
        for _ in range(MAX_PAGES):
            if url is None:
                return
            response = self._send("GET", url)
            page = self._decode("GET", path, response)
            if not isinstance(page, list):
                raise GitHubError(f"GET {path}: expected a list, got {type(page).__name__}")
            yield from page
            match = _NEXT_LINK.search(_header(response.headers, "Link"))
            url = match.group(1) if match else None
        if url is None:
            return
        raise GitHubError(f"GET {path}: more than {MAX_PAGES} pages")

    # -- endpoints -----------------------------------------------------------------

    @property
    def _repo(self) -> str:
        return f"/repos/{self.repository}"

    def list_issue_comments(self, number: int) -> list[dict[str, Any]]:
        """Return every comment on an issue or pull request, oldest first."""
        return list(self.paginate(f"{self._repo}/issues/{number}/comments"))

    def create_comment(self, number: int, body: str) -> dict[str, Any]:
        """Create a comment on an issue or pull request and return it."""
        return self.request("POST", f"{self._repo}/issues/{number}/comments", {"body": body})

    def update_comment(self, comment_id: int, body: str) -> dict[str, Any]:
        """Replace the body of an existing issue comment and return it."""
        return self.request("PATCH", f"{self._repo}/issues/comments/{comment_id}", {"body": body})

    def add_reaction(self, comment_id: int, content: str) -> dict[str, Any]:
        """React to an issue comment (``eyes``, ``+1``, ...)."""
        return self.request(
            "POST", f"{self._repo}/issues/comments/{comment_id}/reactions", {"content": content}
        )

    def get_pull(self, number: int) -> dict[str, Any]:
        """Return one pull request."""
        return self.request("GET", f"{self._repo}/pulls/{number}")

    def get_collaborator_permission(self, login: str) -> str:
        """Return a user's permission on the repository.

        Args:
            login: The GitHub login.

        Returns:
            ``admin``, ``maintain``, ``write``, ``triage``, ``read`` or ``none``
            (``none`` when GitHub answers 404: not a collaborator or no such user).

        Raises:
            GitHubError: On any other failure.
        """
        path = f"{self._repo}/collaborators/{login}/permission"
        try:
            data = self.request("GET", path)
        except GitHubError as exc:
            if exc.status == 404:
                return "none"
            raise
        # role_name distinguishes maintain/triage, which the legacy field folds away.
        role = data.get("role_name") or data.get("permission") or "none"
        return str(role)

    def create_check_run(
        self,
        name: str,
        head_sha: str,
        conclusion: str,
        title: str,
        summary: str,
        text: str = "",
        annotations: Sequence[Mapping[str, Any]] = (),
    ) -> dict[str, Any]:
        """Create a completed check run, sending annotations in batches of 50.

        GitHub accepts at most 50 annotations per request; later batches go out as
        updates of the same run, which append to its annotations.

        Args:
            name: Check-run name shown on the pull request.
            head_sha: The commit the check belongs to (the PR head, not the merge commit).
            conclusion: ``success``, ``neutral`` or ``failure``.
            title: Output title.
            summary: Output summary (Markdown).
            text: Output details (Markdown).
            annotations: GitHub annotation objects.

        Returns:
            The check run as GitHub returned it after the last request.

        Raises:
            GitHubError: If any request fails.
        """
        batches = [
            list(annotations[i : i + ANNOTATION_BATCH])
            for i in range(0, len(annotations), ANNOTATION_BATCH)
        ] or [[]]
        output: dict[str, Any] = {
            "title": title[:255],
            "summary": _cap(summary),
        }
        if text:
            output["text"] = _cap(text)
        first = {
            "name": name,
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": conclusion,
            "output": {**output, "annotations": batches[0]},
        }
        run = self.request("POST", f"{self._repo}/check-runs", first)
        for batch in batches[1:]:
            run = self.update_check_run(run["id"], {**output, "annotations": batch})
        return run

    def update_check_run(self, run_id: int, output: Mapping[str, Any]) -> dict[str, Any]:
        """Update a check run's output (used to append annotation batches)."""
        return self.request("PATCH", f"{self._repo}/check-runs/{run_id}", {"output": dict(output)})


def _cap(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    note = "\n\n(truncated: the full report is in the workflow artifact)"
    return text[: MAX_OUTPUT_CHARS - len(note)] + note
