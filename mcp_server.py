"""
GitHub MCP Server

Exposes GitHub REST API calls as MCP tools over stdio.
Spawned as a subprocess by the AutoGen agent via StdioServerParams.

Tools:
  search_repos     — search repositories by keyword
  get_open_issues  — fetch recent open issues for a repo
"""

import os
from typing import Annotated

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("github-tools")

GITHUB_API = "https://api.github.com"
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if _token := os.getenv("GITHUB_TOKEN"):
    _HEADERS["Authorization"] = f"Bearer {_token}"


@mcp.tool()
async def search_repos(
    query: Annotated[str, "Search keywords, e.g. 'autogen language:python'"],
    max_results: Annotated[int, "Number of repos to return (1-10)"] = 5,
) -> str:
    """Search GitHub repositories by keyword. Returns name, URL, stars, and description."""
    max_results = min(max(1, max_results), 10)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/search/repositories",
            params={"q": query, "per_page": max_results, "sort": "stars"},
            headers=_HEADERS,
            timeout=10,
        )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        return "No repositories found."
    return "\n".join(
        f"{r['full_name']} | ⭐{r['stargazers_count']:,} | {r['html_url']} | {r.get('description') or 'No description'}"
        for r in items
    )


@mcp.tool()
async def get_open_issues(
    owner: Annotated[str, "Repository owner, e.g. 'microsoft'"],
    repo: Annotated[str, "Repository name, e.g. 'autogen'"],
    max_results: Annotated[int, "Number of issues to return (1-10)"] = 5,
) -> str:
    """Fetch the most recent open issues from a GitHub repository."""
    max_results = min(max(1, max_results), 10)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/issues",
            params={"state": "open", "per_page": max_results},
            headers=_HEADERS,
            timeout=10,
        )
    resp.raise_for_status()
    issues = [i for i in resp.json() if "pull_request" not in i]
    if not issues:
        return f"No open issues found for {owner}/{repo}."
    return "\n".join(
        f"#{i['number']} | {i['title']} | {i['html_url']}"
        for i in issues[:max_results]
    )


if __name__ == "__main__":
    mcp.run()
