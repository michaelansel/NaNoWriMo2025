"""A fake GitHub REST server behind the client's Transport, and ai-review builders.

Nothing here reaches the network. The fake keeps comments, check runs and reactions in
memory and records every request so tests can assert on what was sent.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

from nanoif.github.api import Request, Response

REPO = "owner/story"
API = "https://api.example.invalid"
BOT = {"login": "github-actions[bot]", "type": "Bot"}
USER = {"login": "wren-writer", "type": "User"}
HEAD_SHA = "a" * 40
MERGE_SHA = "b" * 40


class FakeGitHub:
    """In-memory GitHub for one repository."""

    def __init__(self, page_size: int = 100) -> None:
        self.page_size = page_size
        self.comments: dict[int, list[dict[str, Any]]] = {}
        self.check_runs: list[dict[str, Any]] = []
        self.reactions: list[tuple[int, str]] = []
        self.permissions: dict[str, dict[str, Any]] = {}
        self.pulls: dict[int, dict[str, Any]] = {}
        self.requests: list[Request] = []
        self.fail: dict[tuple[str, str], int] = {}
        self._next_id = 1000

    # -- helpers for tests --------------------------------------------------------------

    def add_comment(self, pr: int, user: dict[str, str], body: str) -> dict[str, Any]:
        self._next_id += 1
        comment = {
            "id": self._next_id,
            "user": dict(user),
            "body": body,
            "html_url": f"https://example.invalid/c/{self._next_id}",
        }
        self.comments.setdefault(pr, []).append(comment)
        return comment

    def bodies(self, pr: int) -> list[str]:
        return [c["body"] for c in self.comments.get(pr, [])]

    def writes(self) -> list[Request]:
        return [r for r in self.requests if r.method != "GET"]

    # -- transport ----------------------------------------------------------------------

    def __call__(self, request: Request) -> Response:
        self.requests.append(request)
        assert request.timeout > 0, "every request must carry a timeout"
        assert request.headers["Authorization"] == "Bearer test-token"
        parts = urlsplit(request.url)
        assert f"{parts.scheme}://{parts.netloc}" == API
        path = parts.path
        query = parse_qs(parts.query)
        payload = json.loads(request.body) if request.body else None
        for (method, pattern), status in self.fail.items():
            if method == request.method and re.fullmatch(pattern, path):
                return Response(status, {}, b'{"message": "boom"}')
        return self._route(request.method, path, query, payload)

    def _json(self, status: int, data: Any, headers: dict[str, str] | None = None) -> Response:
        return Response(status, headers or {}, json.dumps(data).encode())

    def _route(self, method: str, path: str, query: dict[str, list[str]], payload: Any) -> Response:
        prefix = f"/repos/{REPO}"
        assert path.startswith(prefix), path
        path = path[len(prefix) :]
        if m := re.fullmatch(r"/issues/(\d+)/comments", path):
            pr = int(m.group(1))
            if method == "GET":
                return self._page(path, self.comments.get(pr, []), query)
            assert method == "POST"
            return self._json(201, self.add_comment(pr, BOT, payload["body"]))
        if m := re.fullmatch(r"/issues/comments/(\d+)", path):
            assert method == "PATCH"
            for comments in self.comments.values():
                for comment in comments:
                    if comment["id"] == int(m.group(1)):
                        comment["body"] = payload["body"]
                        return self._json(200, comment)
            return self._json(404, {"message": "Not Found"})
        if m := re.fullmatch(r"/issues/comments/(\d+)/reactions", path):
            self.reactions.append((int(m.group(1)), payload["content"]))
            return self._json(201, {"id": 1, "content": payload["content"]})
        if path == "/check-runs" and method == "POST":
            run = copy.deepcopy(payload)
            run["id"] = len(self.check_runs) + 1
            run["output"]["annotations"] = list(payload["output"].get("annotations", []))
            self.check_runs.append(run)
            return self._json(201, run)
        if m := re.fullmatch(r"/check-runs/(\d+)", path):
            run = self.check_runs[int(m.group(1)) - 1]
            run["output"]["annotations"].extend(payload["output"].get("annotations", []))
            return self._json(200, run)
        if m := re.fullmatch(r"/pulls/(\d+)", path):
            return self._json(200, self.pulls[int(m.group(1))])
        if m := re.fullmatch(r"/collaborators/([^/]+)/permission", path):
            login = m.group(1)
            if login not in self.permissions:
                return self._json(404, {"message": "Not Found"})
            return self._json(200, self.permissions[login])
        raise AssertionError(f"unrouted {method} {path}")

    def _page(self, path: str, items: list[Any], query: dict[str, list[str]]) -> Response:
        assert query.get("per_page") == ["100"]
        page = int(query.get("page", ["1"])[0])
        start = (page - 1) * self.page_size
        chunk = items[start : start + self.page_size]
        headers = {}
        if start + self.page_size < len(items):
            nxt = f"{API}/repos/{REPO}{path}?per_page=100&page={page + 1}"
            headers["Link"] = f'<{nxt}>; rel="next", <{API}/x?page=9>; rel="last"'
        return self._json(200, chunk, headers)


# -- ai-review builders (eval-story names only) ---------------------------------------


def make_finding(
    key: str = "f-1a2b3c4d",
    severity: str = "major",
    editor: str = "continuity",
    description: str = "Tamsin has poled the river for forty years in one passage and thirty in the other.",
    passages: tuple[tuple[str, str], ...] = (("Day 1 EV", "h1"), ("Back at the ferry", "h2")),
    quotes: tuple[tuple[str, str], ...] = (
        ("Day 1 EV", "every working day of those forty years"),
        ("Back at the ferry", "Thirty years I've poled this river"),
    ),
) -> dict[str, Any]:
    return {
        "key": key,
        "editor": editor,
        "type": "number",
        "severity": severity,
        "confidence": "high",
        "description": description,
        "passages": [{"name": n, "hash": h, "file": None, "line": None} for n, h in passages],
        "quotes": [{"passage": p, "text": t} for p, t in quotes],
        "canon_fact_id": None,
        "routes_seen": 1,
    }


def make_editor(
    name: str = "continuity",
    status: str = "ok",
    units: list[dict[str, Any]] | None = None,
    findings: list[dict[str, Any]] | None = None,
    suppressed: list[dict[str, Any]] | None = None,
    unverified: list[dict[str, Any]] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    if units is None:
        units = [
            {"passage": "Day 1 EV", "status": "reviewed", "reason": None, "tokens": 1200},
            {"passage": "Back at the ferry", "status": "reviewed", "reason": None, "tokens": 900},
        ]
    return {
        "name": name,
        "status": status,
        "reason": reason,
        "units": units,
        "findings": findings or [],
        "suppressed": suppressed or [],
        "unverified": unverified or [],
    }


def make_review(*editors: dict[str, Any], mode: str = "changed") -> dict[str, Any]:
    return {
        "version": 1,
        "generated_at": "2026-11-02T10:00:00Z",
        "commit_sha": MERGE_SHA,
        "base_sha": "c" * 40,
        "mode": mode,
        "llm": {
            "profile": "exe",
            "model": "gpt-oss-120b",
            "runner": "exe",
            "calls": 4,
            "prompt_tokens": 12345,
            "completion_tokens": 678,
            "usd": 0.0042,
            "usd_known": True,
        },
        "editors": list(editors) or [make_editor(), make_editor("style")],
    }
