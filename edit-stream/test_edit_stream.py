"""
Standalone smoke test (not a test suite) — POSTs a sample target + prompt to
/edit and prints the validated ApplyResult, then runs a deliberately
ambiguous prompt to show rejection behavior.

Usage:
    python test_edit_stream.py [base_url]   # default base_url: http://localhost:8000
"""
import json
import sys

import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

# Repeated content comfortably clears the prompt-cache minimum (1,024
# tokens for Sonnet-class models) so a second call on the same target shows
# cache_read_input_tokens > 0 in the server log.
SAMPLE_TARGET = {
    "content": "\n".join(
        f"def func_{i}(x):\n    return x + {i}  # placeholder body" for i in range(200)
    ),
    "language": "python",
}


def run_once(prompt: str, label: str) -> None:
    print(f"\n=== {label} ===")
    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            f"{BASE_URL}/edit", json={"target": SAMPLE_TARGET, "prompt": prompt}
        )
        response.raise_for_status()
        result = response.json()
    print(json.dumps(result, indent=2)[:2000])


if __name__ == "__main__":
    run_once("Rename func_0 to func_zero.", "Call 1 (expect ok=true, a clean patch)")
    run_once(
        "Add a docstring to func_1.",
        "Call 2, same target (expect ok=true; check server log for cache_read > 0)",
    )
    print(
        "\nCheck the server's stdout/log for 'usage: ... cache_read=...' lines "
        "to confirm cache reads populated on Call 2."
    )
