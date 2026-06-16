# Viper — Local AI Assistant

A modular, local-first AI assistant running entirely on your machine.
No cloud required. Designed for an RTX 5070 (12 GB VRAM).

## What it does

| Capability | How |
|-----------|-----|
| **RAG** — answer questions about documents | ChromaDB + sentence-transformers + Mistral 7B |
| **Vision** — describe images | LLaVA 7B via Ollama |
| **Code generation** | Mistral 7B via Ollama |
| **Tool / function calling** | Ollama native tool-call API |
| **HTTP API** | FastAPI + Uvicorn |

---

## VRAM Budget

| Component | Model | VRAM |
|-----------|-------|------|
| LLM | mistral:latest (7B Q4_K_M) | ~4.5 GB |
| Vision | llava:7b (Q4_K_M) | ~4.5 GB |
| Embeddings | all-MiniLM-L6-v2 | **CPU** (0 VRAM) |
| CUDA overhead | — | ~1–2 GB |
| **Peak (one model at a time)** | | **~6–7 GB** |

Ollama loads a model on demand and evicts it when idle — the LLM and vision model
never occupy VRAM simultaneously unless you call them at the same time.

---

## Project Structure

```
Viper/
├── app/
│   ├── config.py          ← typed config loader (reads config.yaml)
│   ├── router.py          ← main facade: Viper class
│   ├── rag/
│   │   ├── ingestor.py    ← load & chunk documents
│   │   └── retriever.py   ← ChromaDB vector store + embeddings
│   ├── llm/
│   │   └── inference.py   ← Ollama LLM client
│   ├── vision/
│   │   └── captioner.py   ← Ollama vision (LLaVA) client
│   └── tools/
│       └── executor.py    ← tool registry + agentic loop
├── api/
│   └── main.py            ← FastAPI app
├── data/
│   ├── sample_manual.md   ← sample document (runs out of the box)
│   └── chroma_db/         ← vector store (created automatically)
├── check_env.py           ← verify Python / CUDA / Ollama
├── demo.py                ← end-to-end demo script
├── config.yaml            ← all model names, chunk sizes, etc.
└── requirements.txt
```

---

## Setup

### 1. Python environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 2. Install PyTorch (RTX 5070 — Blackwell sm_120 — requires CUDA 12.6 wheel)

> **Important:** The standard `pip install torch` wheel does **not** support the RTX 5070.
> You must use the CUDA 12.6 index URL.

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
```

### 3. Install remaining dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Ollama

Download and install from **https://ollama.com/download**, then start the server:

```bash
ollama serve          # keep this running in a separate terminal
```

### 5. Pull the models

```bash
ollama pull mistral:latest      # LLM  — ~4.5 GB download
ollama pull llava:7b            # Vision — ~4.5 GB download (only needed for /vision)
```

### 6. Verify the environment

```bash
python check_env.py
```

Expected output: Python version, GPU name + VRAM, Ollama running, all libs OK.

---

## Run the end-to-end demo

```bash
python demo.py
```

This will:
1. Ingest `data/sample_manual.md` into ChromaDB
2. Answer three RAG questions about the manual
3. Run two tool-calling prompts (calculator + datetime)
4. Generate a code snippet via plain chat

---

## Start the API server

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive docs: **http://localhost:8000/docs**

### Example API calls

```bash
# Ingest a document
curl -X POST http://localhost:8000/ingest \
     -H "Content-Type: application/json" \
     -d '{"file_paths": ["data/sample_manual.md"]}'

# Ask a RAG question
curl -X POST http://localhost:8000/ask \
     -H "Content-Type: application/json" \
     -d '{"question": "How do I factory reset the device?"}'

# Plain chat
curl -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Write a Python hello world."}'

# Tool calling
curl -X POST http://localhost:8000/tools \
     -H "Content-Type: application/json" \
     -d '{"message": "What is 1337 * 42 and what time is it?"}'

# Vision (requires llava:7b pulled)
curl -X POST http://localhost:8000/vision \
     -H "Content-Type: application/json" \
     -d '{"image_path": "data/my_image.jpg", "prompt": "What is in this image?"}'
```

---

## Configuration

Edit `config.yaml` to change any setting without touching Python code:

| Key | What it controls |
|-----|-----------------|
| `llm.model` | Ollama model tag for the text LLM |
| `llm.temperature` | Creativity (0 = deterministic, 1 = creative) |
| `llm.max_tokens` | Maximum tokens per LLM response |
| `vision.model` | Ollama model tag for the vision model |
| `embeddings.model` | Sentence-transformers model name |
| `embeddings.device` | `cpu` or `cuda` for embeddings |
| `rag.chunk_size` | Target characters per chunk (smaller = more precise) |
| `rag.chunk_overlap` | Characters shared between adjacent chunks |
| `rag.top_k` | Number of chunks sent to the LLM as context |
| `rag.chroma_persist_dir` | Where ChromaDB stores its files |

---

## Adding your own tools

In any Python file imported before the router (or directly in `app/tools/executor.py`),
decorate a function with `@register_tool`:

```python
from app.tools.executor import register_tool

@register_tool(
    description="Look up the current weather for a city.",
    parameters={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name, e.g. 'London'"},
        },
        "required": ["city"],
    },
)
def get_weather(city: str) -> str:
    # Replace with a real weather API call
    return f"22 °C and sunny in {city}."
```

The LLM will see this tool on every `/tools` request automatically.

---

## Adding your own documents

```bash
# CLI — ingest any .md, .txt, or .pdf file
curl -X POST http://localhost:8000/ingest \
     -H "Content-Type: application/json" \
     -d '{"file_paths": ["path/to/your/manual.pdf"]}'
```

Or from Python:

```python
from app.router import Viper
viper = Viper()
viper.ingest(["path/to/your/manual.pdf"])
```

---

## Swapping components

| To swap | Edit |
|---------|------|
| LLM (different Ollama model) | `config.yaml` → `llm.model` |
| LLM runtime (e.g. vLLM) | `app/llm/inference.py` only |
| Vector store (FAISS, Weaviate) | `app/rag/retriever.py` only |
| Embedding model | `config.yaml` → `embeddings.model` |
| Vision model | `config.yaml` → `vision.model` |
| Document loaders | `app/rag/ingestor.py` only |

---

## Reproduce flow

Follow these steps on a clean checkout to go from zero to a running system.

### 1. Pull pinned base models and build Viper variants

```bash
# From Viper/ (project root)
python scripts/setup_models.py
```

This script is **idempotent** — re-running it is a no-op if nothing has
changed. It will:

1. Verify Ollama is reachable (`ollama serve` must be running)
2. Pull `mistral:7b-instruct-v0.3-q4_K_M` and `llava:7b-v1.6-mistral-q4_K_M`
   if not already cached locally
3. Build `viper-llm`, `viper-llm-tools`, and `viper-vision` from the
   committed Modelfiles in `modelfiles/`

To force a rebuild of all variants (e.g. after editing a Modelfile):

```bash
python scripts/setup_models.py --force
```

### 2. Verify the environment

```bash
python check_env.py           # Python, CUDA, Ollama, models, LLM round-trip
python check_env.py --vision  # also runs vision round-trip (slow — model swap)
```

Expected: all `[PASS]` lines, exit code 0.

### 3. Run the demo

```bash
python demo.py
```

---

## Optional `config.yaml` fields

These fields are new and **optional** — omitting them preserves the existing
behaviour exactly. Existing `config.yaml` files with `temperature` and
`max_tokens` at the top level continue to work unchanged.

| Key | Type | What it controls |
|-----|------|-----------------|
| `llm.system_prompt` | string | Default system prompt; prepended unless the caller already set one |
| `llm.format` | `"json"` | Constrain Ollama output to valid JSON syntax (Ollama ≥ 0.1.9) |
| `llm.options.num_ctx` | int | Context window (default: Modelfile value; >8192 increases VRAM) |
| `llm.options.seed` | int | Fixed RNG seed (pair with `temperature: 0` for determinism) |
| `llm.options.repeat_penalty` | float | Penalise repeated tokens |
| `llm.options.num_predict` | int | Max tokens per response |
| `vision.system_prompt` | string | Default system prompt for vision calls |
| `vision.options.num_ctx` | int | Context window for vision model |
| `vision.options.temperature` | float | Vision model temperature |

**Precedence rule** (highest wins):
`per-call override > config.yaml options > Modelfile PARAMETER default`

Only keys that are explicitly set are forwarded to Ollama. Unset keys fall
through to whatever the Modelfile baked in — so an empty `options:` block
gives full control back to the Modelfile.

Example snippet using the new fields:

```yaml
llm:
  model: "viper-llm"           # custom variant built by setup_models.py
  base_url: "http://localhost:11434"
  # temperature and max_tokens still work here for backward compat
  options:
    num_ctx: 4096
    seed: 42                   # pair with temperature: 0 for determinism

vision:
  model: "viper-vision"
  base_url: "http://localhost:11434"
  system_prompt: "Describe this image for a visually impaired user."
```

---

## What does NOT fit in 12 GB

- **70B models** (even Q4 requires ~35–40 GB) — use a 7B or 13B variant instead.
- **Running LLM + Vision simultaneously** if you load both as Python tensors. Ollama
  handles this by evicting the idle model automatically.
- **LoRA fine-tuning** — not needed for v1. If you add it later, 7B QLoRA training
  fits in 12 GB using `bitsandbytes` + `peft` (4-bit base + 16-bit adapter gradients).
