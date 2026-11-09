"""Minimal GitHub REST client for Skills Hub Git Sync (github.com and GitHub Enterprise Server)."""

import io
import time
from dataclasses import dataclass
from typing import Final
from urllib.parse import quote

import httpx
import jwt

from hangarllm.hangar.skill_sync.types import BranchList, GitConnection, GitRepository, RepositoryList

MAX_ARCHIVE_BYTES: Final = 50 * 1024 * 1024
_MAX_REPO_PAGES: Final = 10
_API_VERSION: Final = "2022-11-28"
_TIMEOUT: Final = httpx.Timeout(30.0, connect=10.0)


@dataclass(frozen=True, slots=True)
class GitHubError:
    status: int
    message: str


@dataclass(frozen=True, slots=True)
class HeadCommit:
    sha: str
    etag: str | None


@dataclass(frozen=True, slots=True)
class NotModified:
    pass


_installation_tokens: dict[tuple[str, str, str], tuple[str, float]] = {}  # mutable-ok: process-wide token cache


def _app_jwt(app_id: str, private_key: str, now: float) -> str:
    return jwt.encode({"iat": int(now) - 60, "exp": int(now) + 540, "iss": app_id}, private_key, algorithm="RS256")


class GitHubClient:
    def __init__(self, connection: GitConnection, client: httpx.AsyncClient) -> None:
        self._connection: Final = connection
        self._client: Final = client
        self._base: Final = connection.api_base_url.rstrip("/")

    def _headers(self, token: str | None, accept: str = "application/vnd.github+json") -> dict[str, str]:
        return {
            "Accept": accept,
            "X-GitHub-Api-Version": _API_VERSION,
            "User-Agent": "HangarLLM-SkillSync",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        }

    async def token(self) -> str | None | GitHubError:
        conn: Final = self._connection
        match conn.auth_type:
            case "none":
                return None
            case "token":
                if conn.token is None or not conn.token.get_secret_value().strip():
                    return GitHubError(400, "A GitHub token is required for this connection")
                return conn.token.get_secret_value().strip()
            case "github_app":
                return await self._installation_token()

    async def _installation_token(self) -> str | GitHubError:
        conn: Final = self._connection
        if not conn.app_id or not conn.installation_id or conn.private_key is None:
            return GitHubError(400, "GitHub App connections need app_id, installation_id and private_key")
        cache_key: Final = (self._base, conn.app_id, conn.installation_id)
        now: Final = time.time()
        cached: Final = _installation_tokens.get(cache_key)
        if cached is not None and cached[1] - 60 > now:
            return cached[0]
        try:
            app_token: Final = _app_jwt(conn.app_id, conn.private_key.get_secret_value(), now)
        except (ValueError, TypeError, jwt.PyJWTError):
            return GitHubError(400, "The GitHub App private key is not a valid PEM RSA key")
        response: Final = await self._request(
            "POST", f"/app/installations/{quote(conn.installation_id, safe='')}/access_tokens", app_token
        )
        if isinstance(response, GitHubError):
            return response
        payload: Final = response.json()
        token: Final = payload.get("token") if isinstance(payload, dict) else None
        if not isinstance(token, str):
            return GitHubError(502, "GitHub did not return an installation token")
        _installation_tokens[cache_key] = (token, now + 3000)
        return token

    async def _request(
        self, method: str, path: str, token: str | None, *, headers: dict[str, str] | None = None
    ) -> httpx.Response | GitHubError:
        try:
            response: Final = await self._client.request(
                method,
                f"{self._base}{path}",
                headers={**self._headers(token), **(headers or {})},
                timeout=_TIMEOUT,
                follow_redirects=False,
            )
        except httpx.HTTPError:
            return GitHubError(502, f"Could not reach {self._base}")
        if response.status_code in (200, 201, 302, 304, 307):
            return response
        return GitHubError(response.status_code, _describe(response))

    async def list_repositories(self) -> RepositoryList | GitHubError:
        token: Final = await self.token()
        if isinstance(token, GitHubError):
            return token
        if token is None:
            return GitHubError(400, "Public connections cannot list repositories; type owner/repository instead")
        listing_path: Final = (
            "/installation/repositories" if self._connection.auth_type == "github_app" else "/user/repos"
        )
        repos: list[GitRepository] = []  # mutable-ok: paginated accumulation
        for page in range(1, _MAX_REPO_PAGES + 1):
            response = await self._request("GET", f"{listing_path}?per_page=100&page={page}&sort=full_name", token)
            if isinstance(response, GitHubError):
                return response
            payload = response.json()
            items = payload.get("repositories", ()) if isinstance(payload, dict) else payload
            repos.extend(_repository(item) for item in items if isinstance(item, dict))
            if 'rel="next"' not in response.headers.get("link", ""):
                return RepositoryList(repositories=tuple(sorted(repos, key=lambda r: r.full_name.lower())))
        return RepositoryList(repositories=tuple(sorted(repos, key=lambda r: r.full_name.lower())), truncated=True)

    async def list_branches(self, owner: str, repository: str) -> BranchList | GitHubError:
        token: Final = await self.token()
        if isinstance(token, GitHubError):
            return token
        response: Final = await self._request("GET", f"{_repo_path(owner, repository)}/branches?per_page=100", token)
        if isinstance(response, GitHubError):
            return response
        payload: Final = response.json()
        names: Final = tuple(
            item["name"] for item in payload if isinstance(item, dict) and isinstance(item.get("name"), str)
        )
        return BranchList(branches=names)

    async def head_commit(
        self, owner: str, repository: str, branch: str, etag: str | None = None
    ) -> HeadCommit | NotModified | GitHubError:
        token: Final = await self.token()
        if isinstance(token, GitHubError):
            return token
        response: Final = await self._request(
            "GET",
            f"{_repo_path(owner, repository)}/commits/{quote(branch, safe='')}",
            token,
            headers={"Accept": "application/vnd.github.sha", **({"If-None-Match": etag} if etag else {})},
        )
        if isinstance(response, GitHubError):
            return response
        if response.status_code == 304:
            return NotModified()
        sha: Final = response.text.strip()
        if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
            return GitHubError(502, "GitHub returned an unexpected commit id")
        return HeadCommit(sha=sha, etag=response.headers.get("etag"))

    async def download_archive(self, owner: str, repository: str, sha: str) -> bytes | GitHubError:
        token: Final = await self.token()
        if isinstance(token, GitHubError):
            return token
        redirect: Final = await self._request("GET", f"{_repo_path(owner, repository)}/zipball/{sha}", token)
        if isinstance(redirect, GitHubError):
            return redirect
        location: Final = redirect.headers.get("location")
        if redirect.status_code == 200:
            return _bounded(redirect.content)
        if not location:
            return GitHubError(502, "GitHub did not return the repository archive")
        same_host: Final = httpx.URL(location).host == httpx.URL(self._base).host
        buffer: Final = io.BytesIO()
        try:
            async with self._client.stream(
                "GET",
                location,
                headers=self._headers(token if same_host else None, accept="application/zip"),
                timeout=_TIMEOUT,
                follow_redirects=False,
            ) as response:
                if response.status_code != 200:
                    return GitHubError(response.status_code, "Could not download the repository archive")
                async for chunk in response.aiter_bytes():
                    if buffer.tell() + len(chunk) > MAX_ARCHIVE_BYTES:
                        return GitHubError(413, "Repository archive is larger than 50 MiB")
                    buffer.write(chunk)
        except httpx.HTTPError:
            return GitHubError(502, "The repository archive download failed")
        return buffer.getvalue()


def _bounded(content: bytes) -> bytes | GitHubError:
    return (
        content if len(content) <= MAX_ARCHIVE_BYTES else GitHubError(413, "Repository archive is larger than 50 MiB")
    )


def _repo_path(owner: str, repository: str) -> str:
    return f"/repos/{quote(owner, safe='')}/{quote(repository, safe='')}"


def _repository(item: dict[str, object]) -> GitRepository:
    owner: Final = item.get("owner")
    owner_login: Final = owner.get("login") if isinstance(owner, dict) else None
    return GitRepository(
        full_name=str(item.get("full_name", "")),
        owner=str(owner_login or ""),
        name=str(item.get("name", "")),
        default_branch=str(item.get("default_branch") or "main"),
        private=bool(item.get("private", False)),
        description=item.get("description") if isinstance(item.get("description"), str) else None,
    )


def _github_message(response: httpx.Response) -> str | None:
    try:
        payload: Final = response.json()
    except ValueError:
        return None
    message: Final = payload.get("message") if isinstance(payload, dict) else None
    return message if isinstance(message, str) else None


def _describe(response: httpx.Response) -> str:
    message: Final = _github_message(response)
    hints: Final = {
        401: "Check the token or GitHub App credentials.",
        403: "The credentials lack access (Contents: read) or the rate limit was hit.",
        404: "Repository, branch or installation not found, or not visible to these credentials.",
    }
    return " ".join(
        p for p in (f"GitHub returned HTTP {response.status_code}.", message, hints.get(response.status_code)) if p
    )


def repository_url(api_base_url: str, owner: str, repository: str) -> str:
    return f"{web_base(api_base_url)}/{owner}/{repository}"


def commit_url(api_base_url: str, owner: str, repository: str, sha: str) -> str:
    return f"{repository_url(api_base_url, owner, repository)}/commit/{sha}"


def web_base(api_base_url: str) -> str:
    base: Final = api_base_url.rstrip("/")
    if base == "https://api.github.com":
        return "https://github.com"
    return base.removesuffix("/api/v3")
