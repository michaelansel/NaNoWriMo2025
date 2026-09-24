"""The REST client: pagination, check-run annotation batches, errors, permissions."""

from __future__ import annotations

import pytest
from github_fakes import API, BOT, HEAD_SHA, REPO, USER, FakeGitHub

from nanoif.github.api import (
    ANNOTATION_BATCH,
    GitHubAPI,
    GitHubConfigError,
    GitHubError,
    Request,
    Response,
)


def test_list_issue_comments_follows_next_links_across_pages():
    fake = FakeGitHub(page_size=2)
    for index in range(5):
        fake.add_comment(7, USER, f"comment {index}")
    api = GitHubAPI("test-token", REPO, api_url=API, transport=fake)
    comments = api.list_issue_comments(7)
    assert [c["body"] for c in comments] == [f"comment {i}" for i in range(5)]
    assert len([r for r in fake.requests if r.method == "GET"]) == 3


def test_every_request_carries_a_timeout_and_api_headers(api, fake):
    api.create_comment(3, "hello")
    request = fake.requests[-1]
    assert request.timeout == pytest.approx(30.0)
    assert request.headers["Accept"] == "application/vnd.github+json"
    assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"


def test_http_error_raises_github_error_with_status(api, fake):
    fake.fail[("POST", r"/repos/owner/story/issues/\d+/comments")] = 403
    with pytest.raises(GitHubError) as excinfo:
        api.create_comment(3, "hello")
    assert excinfo.value.status == 403
    assert "HTTP 403" in str(excinfo.value)


def test_non_json_body_is_an_error():
    api = GitHubAPI("t", REPO, transport=lambda _r: Response(200, {}, b"<html>"))
    with pytest.raises(GitHubError, match="not JSON"):
        api.get_pull(1)


def test_network_failure_from_transport_propagates_as_github_error():
    def broken(request: Request) -> Response:
        raise GitHubError(f"{request.method} {request.url}: timed out")

    api = GitHubAPI("t", REPO, transport=broken)
    with pytest.raises(GitHubError, match="timed out"):
        api.list_issue_comments(1)


def test_missing_token_or_repository_is_a_config_error():
    with pytest.raises(GitHubConfigError, match="GITHUB_TOKEN"):
        GitHubAPI.from_env({"GITHUB_REPOSITORY": REPO})
    with pytest.raises(GitHubConfigError, match="owner/name"):
        GitHubAPI.from_env({"GITHUB_TOKEN": "x", "GITHUB_REPOSITORY": "nonsense"})


def test_from_env_uses_the_api_url_variable():
    api = GitHubAPI.from_env(
        {"GITHUB_TOKEN": "x", "GITHUB_REPOSITORY": REPO, "GITHUB_API_URL": "https://ghe/api/v3/"}
    )
    assert api.api_url == "https://ghe/api/v3"


@pytest.mark.parametrize("count, requests", [(0, 1), (50, 1), (51, 2), (120, 3)])
def test_check_run_annotations_go_out_in_batches_of_50(api, fake, count, requests):
    annotations = [
        {
            "path": "src/EV-20261101.twee",
            "start_line": i + 1,
            "end_line": i + 1,
            "annotation_level": "warning",
            "message": f"m{i}",
        }
        for i in range(count)
    ]
    api.create_check_run("Structure", HEAD_SHA, "neutral", "t", "s", "", annotations)
    writes = fake.writes()
    assert len(writes) == requests
    assert writes[0].method == "POST" and all(w.method == "PATCH" for w in writes[1:])
    run = fake.check_runs[0]
    assert run["head_sha"] == HEAD_SHA and run["status"] == "completed"
    assert run["conclusion"] == "neutral"
    assert [a["message"] for a in run["output"]["annotations"]] == [f"m{i}" for i in range(count)]
    assert ANNOTATION_BATCH == 50


def test_check_run_output_is_capped_to_github_limit(api, fake):
    api.create_check_run("Continuity Editor", HEAD_SHA, "success", "t", "x" * 70000, "y" * 70000)
    output = fake.check_runs[0]["output"]
    assert len(output["summary"]) == 65535 and output["summary"].endswith("workflow artifact)")
    assert len(output["text"]) == 65535


def test_collaborator_permission_prefers_role_name_and_404_is_none(api, fake):
    fake.permissions["wren-writer"] = {"permission": "write", "role_name": "maintain"}
    fake.permissions["reader"] = {"permission": "read", "role_name": "read"}
    assert api.get_collaborator_permission("wren-writer") == "maintain"
    assert api.get_collaborator_permission("reader") == "read"
    assert api.get_collaborator_permission("stranger") == "none"


def test_collaborator_permission_other_errors_raise(api, fake):
    fake.fail[("GET", r"/repos/owner/story/collaborators/.+/permission")] = 500
    with pytest.raises(GitHubError):
        api.get_collaborator_permission("wren-writer")


def test_reaction_and_pull(api, fake):
    fake.pulls[4] = {"number": 4, "head": {"sha": HEAD_SHA}}
    comment = fake.add_comment(4, BOT, "hi")
    api.add_reaction(comment["id"], "eyes")
    assert fake.reactions == [(comment["id"], "eyes")]
    assert api.get_pull(4)["head"]["sha"] == HEAD_SHA
