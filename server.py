"""
FastAPI server — wraps the MCP agent as an HTTP endpoint for ACA.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from gh_agent_mcp import run


class QueryRequest(BaseModel):
    question: str


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required")
    yield


app = FastAPI(
    title="GitHub MCP Agent",
    description="AutoGen agent that queries GitHub via an MCP server and returns JSON.",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")


@app.post("/query")
async def query(request: QueryRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="question cannot be empty")
    try:
        payload = await run(request.question)
        return JSONResponse(content=payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
