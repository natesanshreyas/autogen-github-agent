"""
GitHub Agent — MCP edition

Connects to the GitHub MCP server (mcp_server.py) via stdio,
discovers its tools at runtime, runs an AutoGen AssistantAgent,
and returns a structured JSON payload.

Usage:
    python gh_agent_mcp.py
    python gh_agent_mcp.py "find top LLM agent repos and open issues for microsoft/autogen"
"""

import asyncio
import json
import os
import re
import sys
from typing import Any

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.tools.mcp import StdioServerParams, mcp_server_tools


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of an LLM response string."""
    # Try direct parse first
    try:
        parsed = json.loads(text.strip())
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences and retry
    stripped = re.sub(r"```(?:json)?|```", "", text).strip()
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Last resort: find outermost { }
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    # Couldn't parse — wrap the raw text
    return {"answer": text, "parse_error": "response was not valid JSON"}


# ---------------------------------------------------------------------------
# Core agent runner
# ---------------------------------------------------------------------------

async def run(question: str) -> dict[str, Any]:
    """
    Spawn the GitHub MCP server, run the agent against the question,
    and return a structured JSON payload.
    """
    # Spawn mcp_server.py as a stdio subprocess — tools are discovered at runtime
    server_params = StdioServerParams(
        command=sys.executable,
        args=[str(os.path.join(os.path.dirname(__file__), "mcp_server.py"))],
        env={
            **os.environ,
            "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", ""),
        },
    )

    tools = await mcp_server_tools(server_params)

    model_client = OpenAIChatCompletionClient(
        model="gpt-4o",
        api_key=os.environ["OPENAI_API_KEY"],
    )

    agent = AssistantAgent(
        name="GitHubAgent",
        model_client=model_client,
        tools=tools,
        system_message=(
            "You are a GitHub research agent. "
            "Use the provided tools to answer the question, then return ONLY a JSON object — no prose. "
            "Schema: "
            '{"question": "<original question>", '
            '"answer": "<1-2 sentence summary>", '
            '"data": [<tool results as structured items>], '
            '"tools_called": ["<tool_name>", ...]}'
        ),
    )

    result = await agent.run(
        task=TextMessage(content=question, source="user")
    )

    # Last message from the agent is the final answer
    last_message = result.messages[-1].content if result.messages else ""
    payload = _extract_json(last_message)

    # Always include metadata
    payload.setdefault("question", question)
    payload["tools_available"] = [t.name for t in tools]
    payload["message_count"] = len(result.messages)

    return payload


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    question = (
        " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else (
            "Find the top 3 Python repos about 'LLM agent framework' "
            "and show the 3 most recent open issues for microsoft/autogen."
        )
    )

    print(f"Question: {question}\n")
    payload = await run(question)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
