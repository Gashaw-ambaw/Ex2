"""Tests of the GitHub reader (F5): cleaning a repo link and the two read-only requests, with a fake network."""
import httpx
import pytest

from app.github import GitHubClient, Limited, NotFound, clean_url

TREE = {"tree": [
    {"path": "README.md", "type": "blob", "size": 3000},
    {"path": "docs", "type": "tree"},
    {"path": "docs/SRS.md", "type": "blob", "size": 10},
]}


def client(handler, token=None):
    return GitHubClient(token, http=httpx.Client(transport=httpx.MockTransport(handler)))


# TC-83: a repo link becomes "owner/repo".
@pytest.mark.parametrize("link", [
    "https://github.com/some-user/Ex1_repo",
    "  https://github.com/some-user/Ex1_repo/  ",
    "https://github.com/some-user/Ex1_repo.git",
    "https://github.com/some-user/Ex1_repo/tree/main/docs",
    "https://github.com/some-user/Ex1_repo?tab=readme-ov-file#top",
    "https://GitHub.com/some-user/Ex1_repo",
])
def test_valid_link_tc83(link):
    assert clean_url(link) == "some-user/Ex1_repo"


@pytest.mark.parametrize("link", [
    "", "hello", "https://gitlab.com/a/b", "http://github.com/a/b", "https://github.com/only-owner",
    "https://github.com.evil.test/a/b", "https://evil.test@github.com/a/b", "https://github.com:81/a/b",
    "https://github.com/a/..", "https://github.com/a b/c", "see https://github.com/a/b",
    "https://github.com/a/.git", "https://[bad",
])
def test_invalid_link_tc83(link):
    assert clean_url(link) is None


# TC-85: one request to the API for the tree, one to the raw host for the README.
def test_tree_and_readme_tc85():
    seen = []

    def handler(request):
        seen.append((str(request.url), request.headers.get("authorization")))
        if request.url.host == "api.github.com":
            return httpx.Response(200, json=TREE)
        return httpx.Response(200, content="שלום".encode())

    github = client(handler)
    assert github.tree("a/b") == [("README.md", 3000), ("docs/SRS.md", 10)]
    assert github.readme("a/b", "my docs/README.md") == "שלום"
    assert seen == [
        ("https://api.github.com/repos/a/b/git/trees/HEAD?recursive=1", None),
        ("https://raw.githubusercontent.com/a/b/HEAD/my%20docs/README.md", None),
    ]


def test_token_goes_only_to_the_api_tc85():
    seen = []

    def handler(request):
        seen.append(request.headers.get("authorization"))
        return httpx.Response(200, json=TREE)

    github = client(handler, token=" dummy-token\n")
    github.tree("a/b")
    github.readme("a/b", "README.md")
    assert seen == ["Bearer dummy-token", None]


def test_empty_repo_has_no_files_tc85():
    assert client(lambda request: httpx.Response(409, json={"message": "Git Repository is empty."})).tree("a/b") == []


@pytest.mark.parametrize("reply", [
    httpx.Response(404),
    httpx.Response(451),
    httpx.Response(403, json={"message": "Repository access blocked"}),
], ids=["missing or private", "unavailable", "blocked"])
def test_not_found_tc85(reply):
    with pytest.raises(NotFound):
        client(lambda request: reply).tree("a/b")


@pytest.mark.parametrize("reply", [
    httpx.Response(429),
    httpx.Response(403, headers={"x-ratelimit-remaining": "0"}),
    httpx.Response(403, json={"message": "You have exceeded a secondary rate limit."}),
    httpx.Response(502),
    httpx.Response(200, text="not json"),
], ids=["429", "limit used up", "secondary limit", "server error", "damaged answer"])
def test_limited_tc85(reply):
    with pytest.raises(Limited):
        client(lambda request: reply).tree("a/b")


def test_network_down_tc85():
    def handler(request):
        raise httpx.ConnectTimeout("slow")

    github = client(handler)
    with pytest.raises(Limited):
        github.tree("a/b")
    with pytest.raises(Limited):
        github.readme("a/b", "README.md")
