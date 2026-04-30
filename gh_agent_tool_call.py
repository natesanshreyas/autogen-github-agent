"""
GitHub Tool Call with AutoGen 0.4 — Framework-native tool APIs
==============================================================
Demonstrates the three AutoGen-specific ways to define tools:

  1. FunctionTool       — autogen_core.tools.FunctionTool
                          wraps a plain async function; schema auto-generated
  2. BaseTool subclass  — autogen_core.tools.BaseTool
                          OOP approach: Pydantic models for args/return,
                          override async run(args, cancellation_token)
  3. Direct invocation  — tool.run_json() + CancellationToken
                          call a tool outside an agent (useful for testing)

Key autogen_core APIs used:
  - CancellationToken               cancel in-flight tool calls
  - FunctionTool(func, description) wrap a function as a typed tool
  - BaseTool[ArgsT, ReturnT]        base class for custom tool objects
  - tool.schema                     ToolSchema TypedDict sent to the LLM
  - tool.run_json(args, token)      invoke a tool directly from code
  - tool.return_value_as_string()   format the result for the LLM
  - AssistantAgent(tools=[...])     agent that auto-calls tools
  - Console(agent.run_stream())     streams ToolCallMessage / ToolCallResultMessage

Requirements:
    pip install -r requirements.txt

Usage:
    export OPENAI_API_KEY=sk-...
    export GITHUB_TOKEN=ghp_...   # optional; raises rate limit 60→5,000 req/hr
    python gh_agent_tool_call.py
"""

import asyncio
import json
import os
from typing import Annotated

import httpx
from pydantic import BaseModel, Field

# ── AutoGen core tool APIs ────────────────────────────────────────────────────
from autogen_core import CancellationToken
from autogen_core.tools import BaseTool, FunctionTool

# ── AutoGen agentchat APIs ────────────────────────────────────────────────────
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient

# ─────────────────────────────────────────────────────────────────────────────
# Shared GitHub HTTP helpers
# ─────────────────────────────────────────────────────────────────────────────

GITHUB_API = "https://api.github.com"
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if _token := os.getenv("GITHUB_TOKEN"):
    _HEADERS["Authorization"] = f"Bearer {_token}"


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1 — FunctionTool
# Wrap an async function explicitly with FunctionTool so that:
#   • the description is set on the FunctionTool object, not the docstring
#   • we hold a reference to inspect .schema and call .run_json() directly
# ─────────────────────────────────────────────────────────────────────────────

async def _search_repos_fn(
    query: Annotated[str, "Search keywords, e.g. 'autogen language:python'"],
    max_results: Annotated[int, "Number of repos to return, between 1 and 10"] = 5,
) -> str:
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
        f"- [{r['full_name']}]({r['html_url']})  ⭐{r['stargazers_count']:,}"
        f"  — {r.get('description') or 'No description'}"
        for r in items
    )


# Explicit FunctionTool construction — description lives on the tool object
search_repos_tool = FunctionTool(
    func=_search_repos_fn,
    name="search_github_repos",
    description=(
        "Search GitHub repositories by keyword. "
        "Returns name, URL, star count, and description for each match."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2 — BaseTool subclass
# The canonical OOP pattern: define Pydantic models for args + return value,
# then implement async run(args: ArgsModel, cancellation_token) -> ReturnModel.
# AutoGen derives the full ToolSchema from the Pydantic model field types.
# ─────────────────────────────────────────────────────────────────────────────

class GetIssuesArgs(BaseModel):
    owner: str = Field(description="Repository owner or organisation, e.g. 'microsoft'")
    repo: str = Field(description="Repository name, e.g. 'autogen'")
    max_results: int = Field(default=5, ge=1, le=10, description="Issues to return (1-10)")


class GetIssuesResult(BaseModel):
    issues: list[str] = Field(description="List of formatted issue strings")
    total_returned: int


class GetRepoOpenIssuesTool(BaseTool[GetIssuesArgs, GetIssuesResult]):
    """BaseTool subclass — args/return types are Pydantic models."""

    def __init__(self) -> None:
        super().__init__(
            args_type=GetIssuesArgs,
            return_type=GetIssuesResult,
            name="get_repo_open_issues",
            description=(
                "Fetch the most recent open issues from a GitHub repository. "
                "Returns issue numbers, titles, and URLs."
            ),
        )

    # AutoGen calls this method; cancellation_token lets callers abort the call
    async def run(
        self,
        args: GetIssuesArgs,
        cancellation_token: CancellationToken,
    ) -> GetIssuesResult:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{args.owner}/{args.repo}/issues",
                params={"state": "open", "per_page": args.max_results},
                headers=_HEADERS,
                timeout=10,
            )
        resp.raise_for_status()
        raw = [i for i in resp.json() if "pull_request" not in i]
        formatted = [
            f"#{i['number']} — {i['title']}  ({i['html_url']})"
            for i in raw[: args.max_results]
        ]
        return GetIssuesResult(issues=formatted, total_returned=len(formatted))


issues_tool = GetRepoOpenIssuesTool()


# ─────────────────────────────────────────────────────────────────────────────
# Inspect the ToolSchema AutoGen will send to the LLM
# ─────────────────────────────────────────────────────────────────────────────

def print_tool_schemas() -> None:
    print("=" * 60)
    print("Tool schemas sent to the LLM\n")
    for tool in (search_repos_tool, issues_tool):
        print(f"[{tool.name}]")
        print(json.dumps(tool.schema, indent=2))
        print()


# ─────────────────────────────────────────────────────────────────────────────
# Direct tool invocation via run_json()
# Useful for unit-testing tools without spinning up a full agent.
# ─────────────────────────────────────────────────────────────────────────────

async def demo_direct_tool_call() -> None:
    print("=" * 60)
    print("Direct tool invocation (no agent)\n")

    token = CancellationToken()

    result = await search_repos_tool.run_json(
        {"query": "microsoft autogen language:python", "max_results": 2},
        token,
    )
    print("[FunctionTool] search_github_repos result:")
    print(search_repos_tool.return_value_as_string(result))
    print()

    result2 = await issues_tool.run_json(
        {"owner": "microsoft", "repo": "autogen", "max_results": 3},
        token,
    )
    print("[BaseTool] get_repo_open_issues result:")
    print(issues_tool.return_value_as_string(result2))
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Agent — AssistantAgent with both tools; streams ToolCallMessage events
# ─────────────────────────────────────────────────────────────────────────────

async def run_agent() -> None:
    print("=" * 60)
    print("AssistantAgent with framework-native tools\n")

    model_client = OpenAIChatCompletionClient(
        model="gpt-4o",
        api_key=os.environ["OPENAI_API_KEY"],
    )

    agent = AssistantAgent(
        name="GitHubAssistant",
        model_client=model_client,
        tools=[search_repos_tool, issues_tool],
        system_message=(
            "You are a helpful GitHub assistant. "
            "Always use the provided tools for live GitHub data."
        ),
    )

    user_message = TextMessage(
        content=(
            "Find the top 3 Python repos about 'LLM agent framework', "
            "then show me the 3 most recent open issues for microsoft/autogen."
        ),
        source="user",
    )

    # Console prints each streamed event:
    #   TextMessage, ToolCallMessage, ToolCallResultMessage, TaskResult
    await Console(agent.run_stream(task=user_message))


# ─────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    print_tool_schemas()
    await demo_direct_tool_call()
    await run_agent()


if __name__ == "__main__":
    asyncio.run(main())
