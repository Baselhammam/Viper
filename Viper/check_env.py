"""
Environment verification script.
Run this first to confirm Python, PyTorch/CUDA, and Ollama are all working.
Usage: python check_env.py
"""
import sys


def check_python() -> None:
    print(f"Python: {sys.version}")
    if sys.version_info < (3, 10):
        print("  WARNING: Python 3.10+ recommended.")


def check_pytorch() -> None:
    try:
        import torch

        print(f"PyTorch: {torch.__version__}")
        cuda_ok = torch.cuda.is_available()
        print(f"CUDA available: {cuda_ok}")

        if cuda_ok:
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                total_gb = props.total_memory / (1024 ** 3)
                used_gb = torch.cuda.memory_allocated(i) / (1024 ** 3)
                free_gb = total_gb - used_gb
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
        else:
            print("  No CUDA GPU found — models will run on CPU (very slow for 7B+).")
            print("  RTX 5070 requires: pip install torch --index-url https://download.pytorch.org/whl/cu126")

    except ImportError:
        print("PyTorch NOT installed.")
        print("  RTX 5070: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126")


def check_ollama() -> None:
    try:
        import ollama

        client = ollama.Client()
        models = client.list()
        names = [m.model for m in models.models] if models.models else []
        print(f"Ollama: running  |  models pulled: {names if names else '(none yet)'}")
        if "mistral:latest" not in names:
            print("  Run: ollama pull mistral:latest")
        if not any("llava" in n for n in names):
            print("  Run: ollama pull llava:7b")
    except ImportError:
        print("Ollama SDK NOT installed — run: pip install ollama")
    except Exception as exc:
        print(f"Ollama: NOT reachable ({exc})")
        print("  Install from https://ollama.com, then: ollama serve")


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
            print(f"  {lib}: OK")
        except ImportError:
            print(f"  {lib}: MISSING — run: pip install -r requirements.txt")


if __name__ == "__main__":
    sep = "=" * 56
    print(sep)
    print("  Viper — Environment Check")
    print(sep)

    print("\n[Python]")
    check_python()

    print("\n[PyTorch / CUDA]")
    check_pytorch()

    print("\n[Ollama]")
    check_ollama()

    print("\n[Key Libraries]")
    check_key_libs()

    print(f"\n{sep}")
