"""
Environment verification script.

Run this after setup to confirm Python, PyTorch/CUDA, Ollama, and all
required models are working correctly.

Usage:
    python check_env.py           # standard checks (skips vision round-trip)
    python check_env.py --vision  # also runs vision round-trip (slow — forces
                                  # an LLM→vision model swap on the 12 GB card)

Exit codes:
    0  all checks passed
    1  one or more checks failed (details printed inline)
"""
import argparse
import json
import io
import struct
import sys
import zlib

# ── Failure accumulator ────────────────────────────────────────────────────────
# All checks append here rather than exiting early, so the full picture is
# printed before the script exits.
_failures: list = []

PINNED_BASES    = ["mistral:7b-instruct-v0.3-q4_K_M", "llava:7b-v1.6-mistral-q4_K_M"]
VIPER_VARIANTS  = ["viper-llm", "viper-vision"]
OLLAMA_TIMEOUT  = 10  # seconds; passed through to httpx via ollama.Client(timeout=)


def _pass(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    _failures.append(msg)


def _warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def _model_present(name: str, local_names: set) -> bool:
    """True if `name` or `name:*` is in the local model set."""
    return name in local_names or any(n.startswith(name + ":") for n in local_names)


# ── Checks ────────────────────────────────────────────────────────────────────

def check_python() -> None:
    print(f"  Python: {sys.version}")
    if sys.version_info < (3, 10):
        _warn("Python 3.10+ recommended.")
    else:
        _pass("Python version OK")


def check_pytorch() -> None:
    try:
        import torch
        print(f"  PyTorch: {torch.__version__}")
        cuda_ok = torch.cuda.is_available()
        print(f"  CUDA available: {cuda_ok}")

        if cuda_ok:
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                total_gb = props.total_memory / (1024 ** 3)
                used_gb  = torch.cuda.memory_allocated(i) / (1024 ** 3)
                free_gb  = total_gb - used_gb
                print(f"  GPU {i}: {props.name}")
                print(f"    Total VRAM : {total_gb:.2f} GB")
                print(f"    Used  VRAM : {used_gb:.2f} GB")
                print(f"    Free  VRAM : {free_gb:.2f} GB")
                # RTX 5070 is Blackwell (sm_120) — needs torch >= 2.6 + CUDA 12.6
                cc = f"{props.major}.{props.minor}"
                if props.major >= 12:
                    print(f"    Compute cap: {cc} (Blackwell — confirm torch >= 2.6)")
                else:
                    print(f"    Compute cap: {cc}")
            _pass("PyTorch + CUDA OK")
        else:
            _warn("No CUDA GPU found — models will run on CPU (very slow for 7B+).")
            _warn("RTX 5070: pip install torch --index-url https://download.pytorch.org/whl/cu126")

    except ImportError:
        _fail("PyTorch NOT installed. Run: pip install torch torchvision "
              "--index-url https://download.pytorch.org/whl/cu126")


def check_ollama(run_vision: bool = False) -> None:
    try:
        import ollama
    except ImportError:
        _fail("Ollama SDK NOT installed — run: pip install ollama")
        return

    from app.config import cfg

    # ── Server reachability (with timeout) ────────────────────────────────────
    try:
        client = ollama.Client(timeout=OLLAMA_TIMEOUT)
        resp   = client.list()
        local_names = {m.model for m in (resp.models or [])}
        _pass(f"Ollama reachable (timeout={OLLAMA_TIMEOUT}s). "
              f"Models present: {sorted(local_names) or '(none)'}")
    except Exception as exc:
        _fail(f"Ollama NOT reachable (timeout={OLLAMA_TIMEOUT}s): {exc}")
        _warn("Start Ollama with: ollama serve")
        return  # all remaining checks require the server

    # ── Pinned base models ────────────────────────────────────────────────────
    for base in PINNED_BASES:
        if _model_present(base, local_names):
            _pass(f"Pinned base present: {base}")
        else:
            _fail(f"Pinned base MISSING: {base}  →  run: python scripts/setup_models.py")

    # ── Viper custom variants ─────────────────────────────────────────────────
    for variant in VIPER_VARIANTS:
        if _model_present(variant, local_names):
            _pass(f"Viper variant present: {variant}")
        else:
            _fail(f"Viper variant MISSING: {variant}  →  run: python scripts/setup_models.py")

    # ── LLM round-trip ────────────────────────────────────────────────────────
    try:
        rt = ollama.Client(timeout=OLLAMA_TIMEOUT)
        response = rt.chat(
            model=cfg.llm.model,
            messages=[{"role": "user", "content": "Reply with one word: ready"}],
        )
        reply = (response.message.content or "").strip()
        if reply:
            _pass(f"LLM round-trip OK. Reply: {reply!r}")
        else:
            _fail("LLM round-trip returned empty response.")
    except Exception as exc:
        _fail(f"LLM round-trip FAILED: {exc}")

    # ── JSON round-trip (only when cfg.llm.format is set) ────────────────────
    if cfg.llm.format:
        # NOTE: format constrains JSON *syntax*, not content correctness.
        # Legacy "json" string targets Ollama >= 0.1.9.
        # JSON-schema objects require Ollama >= 0.5.x.
        try:
            rt = ollama.Client(timeout=OLLAMA_TIMEOUT)
            response = rt.chat(
                model=cfg.llm.model,
                messages=[{
                    "role": "user",
                    "content": 'Return a JSON object with key "status" set to "ok".',
                }],
                format=cfg.llm.format,
            )
            raw = response.message.content or ""
            json.loads(raw)
            _pass(f"JSON round-trip OK (format={cfg.llm.format!r}, response is valid JSON).")
        except json.JSONDecodeError as exc:
            _fail(f"JSON round-trip: response is NOT valid JSON: {exc}")
        except Exception as exc:
            _fail(f"JSON round-trip FAILED: {exc}")

    # ── Vision round-trip (opt-in — forces model swap, ~3–10 s on RTX 5070) ──
    if run_vision:
        _run_vision_roundtrip(cfg)
    else:
        _warn("Vision round-trip skipped (forces model swap — pass --vision to enable).")


def _make_minimal_png() -> bytes:
    """
    Generate a minimal valid 1×1 white-pixel PNG using only stdlib.
    No PIL / Pillow dependency — struct + zlib are sufficient.

    PNG structure: 8-byte signature + IHDR chunk + IDAT chunk + IEND chunk.
    Each chunk: 4-byte big-endian length + 4-byte type + data + 4-byte CRC32.
    """
    def chunk(type_: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(type_ + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + type_ + data + struct.pack(">I", crc)

    # IHDR: width=1, height=1, bit_depth=8, color_type=2 (RGB),
    #       compression=0, filter=0, interlace=0  — total 13 bytes
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    # IDAT: filter byte 0x00 (None) + three 0xFF bytes (RGB white)
    idat = chunk(b"IDAT", zlib.compress(b"\x00\xFF\xFF\xFF"))
    iend = chunk(b"IEND", b"")
    return b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend


def _run_vision_roundtrip(cfg) -> None:
    import base64, os, tempfile

    try:
        import ollama
    except ImportError:
        _fail("Ollama SDK not available for vision round-trip.")
        return

    tmp_path = None
    try:
        png_bytes = _make_minimal_png()
        fd, tmp_path = tempfile.mkstemp(suffix=".png")
        os.write(fd, png_bytes)
        os.close(fd)

        b64_image = base64.b64encode(png_bytes).decode("utf-8")
        rt = ollama.Client(timeout=OLLAMA_TIMEOUT)
        response = rt.chat(
            model=cfg.vision.model,
            messages=[{
                "role": "user",
                "content": "What colour is this image?",
                "images": [b64_image],
            }],
        )
        reply = (response.message.content or "").strip()
        if reply:
            _pass(f"Vision round-trip OK. Reply: {reply[:80]!r}")
        else:
            _fail("Vision round-trip returned empty response.")
    except Exception as exc:
        _fail(f"Vision round-trip FAILED: {exc}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def check_key_libs() -> None:
    libs = [
        "chromadb",
        "sentence_transformers",
        "langchain",
        "fastapi",
        "uvicorn",
        "yaml",
        "pydantic",
    ]
    for lib in libs:
        try:
            __import__(lib)
            _pass(f"{lib}: OK")
        except ImportError:
            _fail(f"{lib}: MISSING — run: pip install -r requirements.txt")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Viper environment check.")
    parser.add_argument(
        "--vision", action="store_true",
        help=(
            "Also run vision round-trip test.  "
            "Forces an LLM→vision model swap which takes ~3–10 s on an RTX 5070."
        ),
    )
    args = parser.parse_args()

    sep = "=" * 56
    print(sep)
    print("  Viper — Environment Check")
    print(sep)

    print("\n[Python]")
    check_python()

    print("\n[PyTorch / CUDA]")
    check_pytorch()

    print("\n[Ollama + Models]")
    check_ollama(run_vision=args.vision)

    print("\n[Key Libraries]")
    check_key_libs()

    print(f"\n{sep}")
    if _failures:
        print(f"  RESULT: {len(_failures)} failure(s) detected:")
        for f in _failures:
            print(f"    ✗ {f}")
        print(sep)
        sys.exit(1)
    else:
        print("  RESULT: All checks passed.")
        print(sep)
