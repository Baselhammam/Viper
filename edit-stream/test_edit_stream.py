"""
Standalone smoke test (not a test suite) — POSTs a sample target + prompt to
/edit twice (to show prompt-cache reads on the 2nd call) and prints the
streamed EditOps as they arrive.

Usage:
    python test_edit_stream.py [base_url]   # default base_url: http://localhost:8000
"""
import json
import sys
import time

import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

# Target content is repeated to comfortably clear the prompt-cache minimum
# (1024 tokens for Sonnet-class models) so the 2nd call's cache_read_input_tokens
# is non-zero and visible in the server logs.
SAMPLE_TARGET = {
    "content": "\n".join(
        f"def func_{i}(x):\n    return x + {i}  # placeholder body" for i in range(200)
    ),
    "language": "python",
}


def run_once(prompt: str, label: str) -> None:
    print(f"\n=== {label} ===")
    start = time.monotonic()
    with httpx.Client(timeout=60.0) as client:
        with client.stream(
            "POST",
            f"{BASE_URL}/edit",
            json={"target": SAMPLE_TARGET, "prompt": prompt},
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = json.loads(line[len("data:"):].strip())
                print(f"  EditOp: {payload}")
    print(f"  (elapsed {time.monotonic() - start:.2f}s)")


if __name__ == "__main__":
    run_once("Rename func_0 to func_zero.", "Call 1 (expect cache_creation, no cache_read)")
    run_once("Add a docstring to func_1.", "Call 2, same target (expect cache_read > 0)")
    print(
        "\nCheck the server's stdout/log for 'final usage: ... cache_read=...' lines "
        "to confirm cache reads populated on Call 2."
    )
