"""
GitHub Tool Call with AutoGen 0.4

Demonstrates an AssistantAgent using FunctionTool to call the GitHub REST API.
Type hints and docstrings on each function are used to auto-generate the tool
schema sent to the LLM — no manual JSON schema required.

Requirements:
    pip install -r requirements.txt

Usage:
    Set environment variables before running:
        OPENAI_API_KEY=<your key>
        GITHUB_TOKEN=<your personal access token>
            optional — raises rate limit from 60 to 5,000 req/hr

    python gh_agent_tool_call.py
"""

import asyncio
import os
from typing import Annotated

import httpx
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient

# ---------------------------------------------------------------------------
# GitHub client setup
# ---------------------------------------------------------------------------

GITHUB_API = "https://api.github.com"

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if token := os.getenv("GITHUB_TOKEN"):
    HEADERS["Authorization"] = f"Bearer {token}"


# ---------------------------------------------------------------------------
# Tools
#
# Each plain Python function becomes a tool available to the agent.
# Annotated type hints provide per-parameter descriptions; the docstring
# becomes the tool description. AutoGen converts these into the JSON schema
# the LLM receives — no manual schema writing needed.
# ---------------------------------------------------------------------------

def search_github_repos(
    query: Annotated[str, "Search keywords, e.g. 'autogen language:python'"],
    max_results: Annotated[int, "Maximum number of repos to return (1–10)"] = 5,
) -> str:
    """Search GitHub repositories and return their names, descriptions, and star counts."""
    max_results = min(max(1, max_results), 10)
    resp = httpx.get(
        f"{GITHUB_API}/search/repositories",
        params={"q": query, "per_page": max_results, "sort": "stars"},
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        return "No repositories found."
    return "\n".join(
        f"- [{r['full_name']}]({r['html_url']})  ⭐{r['stargazers_count']:,}"
        f"  — {r.get('description') or 'No description'}"
        for r in items
    )


def get_repo_open_issues(
    owner: Annotated[str, "Repository owner / organisation, e.g. 'microsoft'"],
    repo: Annotated[str, "Repository name, e.g. 'autogen'"],
    max_results: Annotated[int, "Maximum number of issues to return (1–10)"] = 5,
) -> str:
    """Fetch the most recent open issues from a GitHub repository."""
    max_results = min(max(1, max_results), 10)
    resp = httpx.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/issues",
        params={"state": "open", "per_page": max_results},
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    issues = [i for i in resp.json() if "pull_request" not in i]
    if not issues:
        return f"No open issues found for {owner}/{repo}."
    return "\n".join(
        f"#{i['number']} — {i['title']}  ({i['html_url']})"
        for i in issues[:max_results]
    )


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

async def main() -> None:
    model_client = OpenAIChatCompletionClient(
        model="gpt-4o",
        api_key=os.environ["OPENAI_API_KEY"],
    )

    agent = AssistantAgent(
        name="GitHubAssistant",
        description="An assistant that can search GitHub and inspect repositories.",
        model_client=model_client,
        tools=[search_github_repos, get_repo_open_issues],
        system_message=(
            "You are a helpful GitHub assistant. "
            "Use the provided tools to answer questions about GitHub repositories. "
            "Always prefer tool results over general knowledge for live data."
        ),
    )

    user_message = TextMessage(
        content=(
            "Find the top 3 Python repos related to 'LLM agent framework', "
            "then show me the 3 most recent open issues for microsoft/autogen."
        ),
        source="user",
    )

    await Console(agent.run_stream(task=user_message))


if __name__ == "__main__":
    asyncio.run(main())
