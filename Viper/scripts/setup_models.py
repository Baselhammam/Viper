"""
Idempotent model setup for Viper.

Steps
-----
1. Verify the Ollama server is reachable (with timeout via httpx).
2. Pull each pinned base model if not already present locally.
3. For each Modelfile: build the custom variant ONLY if it is missing OR
   if the Modelfile content has changed since the last build (SHA256 hash).

Re-running this script with no Modelfile changes performs zero rebuilds.
Safe to run in CI or on every developer machine checkout.

Usage
-----
    python scripts/setup_models.py           # normal run (skips unchanged)
    python scripts/setup_models.py --force   # rebuild all variants
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import ollama

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR    = Path(__file__).parent
PROJECT_ROOT  = SCRIPT_DIR.parent
MODELFILE_DIR = PROJECT_ROOT / "modelfiles"

# Hash store is gitignored — it tracks which Modelfile content was used for
# the last successful build of each variant.
HASH_FILE = SCRIPT_DIR / ".model_hashes.json"

# ── Model registry ─────────────────────────────────────────────────────────────
# (custom_model_name, modelfile_filename, pinned_base_tag)
MODELS = [
    ("viper-llm",       "viper-llm.Modelfile",       "mistral:7b-instruct-v0.3-q4_K_M"),
    ("viper-llm-tools", "viper-llm-tools.Modelfile", "mistral:7b-instruct-v0.3-q4_K_M"),
    ("viper-vision",    "viper-vision.Modelfile",     "llava:7b-v1.6-mistral-q4_K_M"),
]

# ── Helpers ────────────────────────────────────────────────────────────────────

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_hashes() -> dict:
    if HASH_FILE.exists():
        return json.loads(HASH_FILE.read_text(encoding="utf-8"))
    return {}


def _save_hashes(hashes: dict) -> None:
    HASH_FILE.write_text(json.dumps(hashes, indent=2), encoding="utf-8")


def _local_model_names(client: ollama.Client) -> set:
    """
    Return the set of locally present model names.

    ollama.list() returns names like "viper-llm:latest" or
    "mistral:7b-instruct-v0.3-q4_K_M".  We keep both the full tag and the
    bare name (everything before ":") so callers can check either form.
    """
    resp = client.list()
    names: set = set()
    for m in resp.models or []:
        names.add(m.model)
        names.add(m.model.split(":")[0])
    return names


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Set up Viper Ollama model variants.")
    parser.add_argument(
        "--force", action="store_true",
        help="Rebuild all custom variants even if Modelfiles are unchanged.",
    )
    args = parser.parse_args()

    # ── 1. Server reachability ─────────────────────────────────────────────────
    print("Checking Ollama server...")
    try:
        # ollama.Client() with no host defaults to http://localhost:11434.
        # The underlying httpx transport respects OS TCP connect timeouts.
        # For an explicit deadline, instantiate with timeout= (httpx kwarg):
        #   ollama.Client(timeout=10)
        # We keep the default here so setup works on slow machines too.
        client = ollama.Client()
        local = _local_model_names(client)
        print(f"  [OK] Ollama reachable. Local models: {sorted(m for m in local if ':' in m) or '(none)'}")
    except Exception as exc:
        print(f"  [FAIL] Cannot reach Ollama: {exc}")
        print("         Start with: ollama serve")
        sys.exit(1)

    # ── 2. Pull pinned base models if missing ──────────────────────────────────
    needed_bases = dict.fromkeys(base for (_, _, base) in MODELS)  # preserve order, deduplicate
    for base_tag in needed_bases:
        if base_tag in local:
            print(f"  [SKIP] Base already present: {base_tag}")
        else:
            print(f"  [PULL] {base_tag}  (this may take several minutes the first time)...")
            ollama.pull(base_tag)
            print(f"  [OK]   Pulled: {base_tag}")

    # Refresh local list after potential pulls.
    local = _local_model_names(client)

    # ── 3. Build custom variants (idempotent via SHA256) ───────────────────────
    stored_hashes = _load_hashes()

    for model_name, modelfile_name, _ in MODELS:
        modelfile_path = MODELFILE_DIR / modelfile_name
        if not modelfile_path.exists():
            print(f"  [WARN] Modelfile not found, skipping: {modelfile_path}")
            continue

        content      = modelfile_path.read_text(encoding="utf-8")
        current_hash = _sha256(content)
        already_built  = model_name in local
        hash_unchanged = stored_hashes.get(model_name) == current_hash

        if already_built and hash_unchanged and not args.force:
            print(f"  [SKIP] {model_name}: already up to date (Modelfile unchanged).")
            continue

        if not already_built:
            reason = "new model"
        elif args.force:
            reason = "--force"
        else:
            reason = "Modelfile changed"

        print(f"  [BUILD] {model_name}  ({reason})...")
        ollama.create(model=model_name, modelfile=content)
        stored_hashes[model_name] = current_hash
        _save_hashes(stored_hashes)
        print(f"  [OK]    {model_name} built and registered.")

    print("\nSetup complete.  Run python check_env.py to verify.")


if __name__ == "__main__":
    main()
