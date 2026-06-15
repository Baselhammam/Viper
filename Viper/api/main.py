"""
Optional FastAPI adapter for the backend capabilities layer.

Primary usage of the backend is IN-PROCESS:
    from capabilities import get_llm, get_rag, get_mcp

This adapter is for when the pipeline runs as a SEPARATE PROCESS and
needs to call the backend over HTTP.  Enable it with:
    api.enabled: true  in config.yaml
Then start with:
    python run_api.py

Interactive API docs (when running):
    http://localhost:8000/docs   (Swagger UI)
    http://localhost:8000/redoc  (ReDoc)

Design rule: every route is a one-liner that calls the facade.
No business logic lives here — it's pure HTTP plumbing.
"""
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import capabilities as caps
from app.config import cfg


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm singletons on startup to avoid cold-start latency on first request."""
    if cfg.api.enabled:
        caps.get_embeddings()   # sentence-transformers loads here (~2-5 s)
        caps.get_rag()          # ChromaDB connects here (fast)
        # LLM and vision are Ollama-backed — no Python-side startup cost.
    yield


app = FastAPI(
    title="Viper Backend Capabilities",
    description=(
        "Stateless capabilities layer: LLM, Vision, RAG, Embeddings, MCP.\n\n"
        "Enable via `api.enabled: true` in config.yaml."
    ),
    version="0.2.0",
    lifespan=lifespan,
)


def _check_enabled() -> None:
    if not cfg.api.enabled:
        raise HTTPException(
            status_code=503,
            detail="API adapter is disabled (api.enabled: false in config.yaml).",
        )


# ── Request / Response models ──────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    prompt: str
    system: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

class ChatRequest(BaseModel):
    messages: List[dict]
    tools: Optional[List[dict]] = None

class IngestRequest(BaseModel):
    file_paths: List[str]

class RetrieveRequest(BaseModel):
    query: str
    top_k: Optional[int] = None

class EmbedRequest(BaseModel):
    texts: List[str]

class VisionRequest(BaseModel):
    image_path: str
    prompt: str = "Describe this image in detail."

class ToolCallRequest(BaseModel):
    name: str
    args: dict = {}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Server and config status check."""
    return {
        "status": "ok",
        "api_enabled": cfg.api.enabled,
        "llm_model": cfg.llm.model,
        "vision_model": cfg.vision.model,
        "rag_chunks": caps.get_rag().count() if cfg.api.enabled else None,
    }


# ── LLM ───────────────────────────────────────────────────────────────────────

@app.post("/llm/generate", summary="Single-prompt text generation")
async def llm_generate(req: GenerateRequest):
    _check_enabled()
    try:
        return {"text": caps.get_llm().generate(
            req.prompt, req.system, req.temperature, req.max_tokens
        )}
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post("/llm/chat", summary="Multi-turn chat")
async def llm_chat(req: ChatRequest):
    _check_enabled()
    try:
        return {"text": caps.get_llm().chat(req.messages, req.tools)}
    except Exception as exc:
        raise HTTPException(500, str(exc))


# ── Vision ────────────────────────────────────────────────────────────────────

@app.post("/vision/describe", summary="Describe an image")
async def vision_describe(req: VisionRequest):
    _check_enabled()
    try:
        return {"description": caps.get_vision().describe(req.image_path, req.prompt)}
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post("/vision/ocr", summary="Extract text from an image")
async def vision_ocr(req: VisionRequest):
    _check_enabled()
    try:
        return {"text": caps.get_vision().ocr(req.image_path)}
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))


# ── Embeddings ────────────────────────────────────────────────────────────────

@app.post("/embeddings/embed", summary="Embed a list of texts")
async def embeddings_embed(req: EmbedRequest):
    _check_enabled()
    try:
        vectors = caps.get_embeddings().embed(req.texts)
        return {"vectors": vectors, "dimension": caps.get_embeddings().dimension}
    except Exception as exc:
        raise HTTPException(500, str(exc))


# ── RAG ───────────────────────────────────────────────────────────────────────

@app.post("/rag/ingest", summary="Ingest documents into the knowledge base")
async def rag_ingest(req: IngestRequest):
    _check_enabled()
    try:
        count = caps.get_rag().ingest(req.file_paths)
        return {"chunks_stored": count, "total_chunks": caps.get_rag().count()}
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post("/rag/retrieve", summary="Retrieve relevant chunks for a query")
async def rag_retrieve(req: RetrieveRequest):
    _check_enabled()
    try:
        chunks = caps.get_rag().retrieve(req.query, req.top_k)
        return {"chunks": chunks, "count": len(chunks)}
    except Exception as exc:
        raise HTTPException(500, str(exc))


# ── MCP ───────────────────────────────────────────────────────────────────────

@app.get("/mcp/tools", summary="List all registered MCP tools")
async def mcp_list_tools():
    _check_enabled()
    return {"tools": caps.get_mcp().list_tools()}


@app.post("/mcp/call", summary="Call a registered MCP tool")
async def mcp_call(req: ToolCallRequest):
    _check_enabled()
    try:
        result = caps.get_mcp().call(req.name, req.args)
        return {"result": result}
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))
