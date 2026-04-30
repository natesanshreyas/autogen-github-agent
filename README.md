# AutoGen GitHub Agent

AutoGen 0.4 `AssistantAgent` using `FunctionTool` to call the GitHub REST API.

Demonstrates how plain Python functions — annotated with type hints and docstrings — are automatically converted into tool schemas the LLM can reason over and invoke. No manual JSON schema required.

## Tools

| Tool | Description |
|---|---|
| `search_github_repos` | Search repos by keyword, returns names, descriptions, star counts |
| `get_repo_open_issues` | Fetch recent open issues for a given owner/repo |

## Setup

```bash
pip install -r requirements.txt
```

Set environment variables:

```bash
export OPENAI_API_KEY=<your key>
export GITHUB_TOKEN=<your personal access token>   # optional, raises rate limit 60 → 5,000 req/hr
```

## Run

```bash
python gh_agent_tool_call.py
```

## How it works

Each Python function is passed directly to `AssistantAgent(tools=[...])`. AutoGen reads the `Annotated` type hints for per-parameter descriptions and the docstring for the tool description, then generates the JSON schema that gets sent to the LLM automatically.

The agent receives a user message, reasons over the available tool schemas, decides which to call and with what arguments, receives the result, and continues until it has a final answer — all streamed to the console via `Console(agent.run_stream(...))`.
