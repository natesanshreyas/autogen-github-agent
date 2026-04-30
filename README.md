# AutoGen GitHub Agent

AutoGen 0.4 agents calling GitHub via two approaches — direct `FunctionTool`/`BaseTool` and an MCP server.

## Files

| File | Description |
|---|---|
| `gh_agent_tool_call.py` | `FunctionTool` and `BaseTool` patterns — tools defined directly in Python |
| `mcp_server.py` | GitHub MCP server (FastMCP over stdio) — exposes `search_repos` and `get_open_issues` as MCP tools |
| `gh_agent_mcp.py` | Agent that spawns the MCP server, discovers tools at runtime, returns a JSON payload |
| `server.py` | FastAPI wrapper — exposes `POST /query` for ACA deployment |
| `terraform/` | Terraform for Azure Container Apps deployment |

## MCP approach

The agent spawns `mcp_server.py` as a subprocess via `StdioServerParams`. AutoGen discovers the available tools from the server at runtime, runs the agent, and returns a structured JSON payload:

```json
{
  "question": "...",
  "answer": "...",
  "data": [...],
  "tools_called": ["search_repos", "get_open_issues"],
  "tools_available": ["search_repos", "get_open_issues"],
  "message_count": 6
}
```

## Setup

```bash
pip install -r requirements.txt

export OPENAI_API_KEY=sk-...
export GITHUB_TOKEN=ghp_...   # optional
```

## Run locally

```bash
# MCP agent — returns JSON payload
python gh_agent_mcp.py
python gh_agent_mcp.py "find top rust web framework repos"

# HTTP server
uvicorn server:app --reload --port 8000
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "top LLM agent repos"}'
```

## Deploy to Azure Container Apps

### 1. Provision infrastructure

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# fill in terraform.tfvars

terraform init
terraform apply
```

### 2. Build and push image

```bash
ACR=$(terraform output -raw acr_login_server)
az acr login --name $ACR

docker build -t $ACR/github-mcp-agent:latest ..
docker push $ACR/github-mcp-agent:latest
```

### 3. Trigger new revision

```bash
az containerapp update \
  --name github-mcp-agent \
  --resource-group github-agent-rg \
  --image $ACR/github-mcp-agent:latest
```

App URL is in `terraform output app_url`. Query endpoint: `POST <url>/query`.

## Terraform resources

| Resource | Purpose |
|---|---|
| Resource group | Container for all resources |
| Log Analytics workspace | Required by Container App Environment |
| Container Registry (ACR) | Stores Docker image |
| Container App Environment | ACA runtime environment |
| Container App | Runs the agent, scales to 0 when idle |
