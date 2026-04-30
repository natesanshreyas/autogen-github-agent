# AutoGen GitHub Agent

AutoGen 0.4 `AssistantAgent` demonstrating the three framework-native ways to define tools.

## Tool patterns covered

| Pattern | Class | When to use |
|---|---|---|
| `FunctionTool` | `autogen_core.tools.FunctionTool` | Wrap an existing async function; hold a reference to inspect `.schema` or call `.run_json()` directly |
| `BaseTool` subclass | `autogen_core.tools.BaseTool` | OOP approach with Pydantic models for args and return type; full type safety |
| Direct invocation | `tool.run_json()` + `CancellationToken` | Test tools outside an agent |

## Key APIs

```python
from autogen_core import CancellationToken
from autogen_core.tools import BaseTool, FunctionTool

tool.schema                        # ToolSchema TypedDict sent to the LLM
tool.run_json(args_dict, token)    # invoke directly from code
tool.return_value_as_string(result)# format result for display
```

## Setup

```bash
pip install -r requirements.txt
```

```bash
export OPENAI_API_KEY=sk-...
export GITHUB_TOKEN=ghp_...   # optional — raises rate limit 60 → 5,000 req/hr
```

## Run

```bash
python gh_agent_tool_call.py
```

Output:
1. Tool schemas printed — exactly what gets sent to the LLM
2. Direct tool invocation without an agent
3. Full agent run streaming `ToolCallMessage` / `ToolCallResultMessage` / `TaskResult`
